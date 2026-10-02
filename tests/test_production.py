"""Tests de `src/production.py` (lots simulés, scoring d'un cycle, journal des scores) et de la
sélection du cycle courant par l'exporteur de dérive. Données synthétiques uniquement."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.drift import psi
from src.features import FEATURES_V2
from src.production import (
    COLONNES_CONNUES_APRES_COUP, COLONNES_EXPORT, _nombre_en_texte, ajouter_au_journal,
    entree_journal, lire_journal, preparer_lot, purger_scores, scorer_cycle, simuler_export_mensuel,
    version_fichier,
)

RACINE = Path(__file__).resolve().parents[1]


def silver_synthetique(n: int = 300, graine: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(graine)
    sieges = rng.integers(2, 50, n).astype(float)
    actifs = np.minimum(sieges, rng.integers(0, 50, n)).astype(float)
    return pd.DataFrame({
        "client_id": [f"CLI-{i:06d}" for i in range(n)],
        "date_souscription": pd.Timestamp("2024-01-01") + pd.to_timedelta(rng.integers(0, 600, n), unit="D"),
        "jour_souscription": "lundi",
        "secteur": rng.choice(["Tech", "Finance"], n),
        "pays": "France",
        "taille_entreprise": rng.choice(["TPE", "PME"], n),
        "plan": rng.choice(["Starter", "Pro"], n),
        "anciennete_mois": rng.integers(1, 36, n).astype(float),
        "sieges_souscrits": sieges,
        "utilisateurs_actifs": actifs,
        "taux_adoption_pct": np.round(100 * actifs / sieges, 1),
        "connexions_30j": rng.integers(0, 400, n).astype(float),
        "heures_usage_30j": rng.uniform(0, 200, n).round(1),
        "fonctionnalites_total": 16.0,
        "fonctionnalites_utilisees": rng.integers(0, 16, n).astype(float),
        "nb_integrations": rng.integers(0, 8, n).astype(float),
        "derniere_connexion_jours": rng.integers(0, 60, n).astype(float),
        "tickets_support_90j": rng.integers(0, 12, n).astype(float),
        "delai_reponse_support_h": rng.uniform(1, 40, n).round(1),
        "csat": rng.integers(1, 6, n).astype(float),
        "retards_paiement_12m": rng.integers(0, 3, n).astype(float),
        "revenu_mensuel_recurrent_eur": rng.uniform(20, 12000, n).round(2),
        "couleur_theme_interface": "sombre",
        "code_datacenter": "eu-w1",
        "groupe_experimentation": "control",
        "commentaire_csm": "",
        "sante_compte_fin_periode": rng.integers(0, 100, n).astype(float),
        "valeur_vie_client_eur": rng.uniform(100, 50000, n).round(0),
        "churn": rng.integers(0, 2, n).astype(float),
    })


def catalogue_synthetique() -> pd.DataFrame:
    return pd.DataFrame({
        "plan": ["STARTER", "PRO"], "prix_mensuel_par_siege_eur": ["12", "25"],
        "fonctionnalites_incluses": ["8", "16"], "sla_reponse_h": ["24", "12"],
        "quota_stockage_go": ["10", "100"], "support_dedie": ["Non", "Non"],
    })


def en_nombres(export: pd.DataFrame, colonne: str) -> pd.Series:
    return pd.to_numeric(export[colonne].replace("", np.nan))


class TestSimulerExportMensuel:
    def test_mode_inconnu_refuse(self):
        with pytest.raises(ValueError):
            simuler_export_mensuel(silver_synthetique(), "inconnu")

    def test_deterministe_pour_une_graine(self):
        silver = silver_synthetique()
        assert simuler_export_mensuel(silver, "stable", 7).equals(simuler_export_mensuel(silver, "stable", 7))
        assert not simuler_export_mensuel(silver, "stable", 7).equals(simuler_export_mensuel(silver, "stable", 8))

    def test_format_de_l_export_brut_et_etiquettes_vides(self):
        export = simuler_export_mensuel(silver_synthetique(), "stable")
        assert list(export.columns) == COLONNES_EXPORT
        assert export.map(lambda valeur: isinstance(valeur, str)).all().all()
        for colonne in COLONNES_CONNUES_APRES_COUP:
            assert (export[colonne] == "").all()

    def test_anciennete_avance_d_un_mois(self):
        silver = silver_synthetique()
        export = simuler_export_mensuel(silver, "stable")
        assert (en_nombres(export, "anciennete_mois") == silver["anciennete_mois"] + 1).all()

    def test_derive_applique_la_baisse_d_engagement_du_notebook(self):
        silver = silver_synthetique()
        stable = simuler_export_mensuel(silver, "stable", 3)
        derive = simuler_export_mensuel(silver, "derive", 3)
        assert (en_nombres(derive, "derniere_connexion_jours") == en_nombres(stable, "derniere_connexion_jours") + 30).all()
        assert (en_nombres(derive, "nb_integrations") == (en_nombres(stable, "nb_integrations") - 1).clip(lower=0)).all()
        assert (en_nombres(derive, "csat") == (en_nombres(stable, "csat") - 1).clip(lower=1)).all()
        assert en_nombres(derive, "heures_usage_30j").sum() < 0.65 * en_nombres(stable, "heures_usage_30j").sum()

    def test_lot_stable_sans_derive_lot_derive_en_alerte(self):
        silver = silver_synthetique(n=2000)
        stable = simuler_export_mensuel(silver, "stable")
        derive = simuler_export_mensuel(silver, "derive")
        reference = silver["derniere_connexion_jours"]
        assert psi(silver["connexions_30j"], en_nombres(stable, "connexions_30j")) < 0.10
        assert psi(reference, en_nombres(stable, "derniere_connexion_jours")) < 0.10
        assert psi(reference, en_nombres(derive, "derniere_connexion_jours")) > 0.25

    def test_export_relu_par_la_chaine_d_entrainement(self, tmp_path):
        silver = silver_synthetique()
        chemin = tmp_path / "export_crm.csv"
        simuler_export_mensuel(silver, "derive").to_csv(chemin, index=False)
        X, client_ids = preparer_lot(chemin, catalogue_synthetique())
        assert list(X.columns) == FEATURES_V2
        assert len(X) == len(silver)
        assert client_ids.tolist() == silver["client_id"].tolist()

    def test_nombres_ecrits_sans_perte(self):
        assert _nombre_en_texte(3.0) == "3"
        assert _nombre_en_texte(12345.67) == "12345.67"
        assert _nombre_en_texte(np.nan) == ""


class ModeleChurnFactice:
    def predict_proba(self, X):
        p = np.linspace(0.05, 0.95, len(X))
        return np.column_stack([1 - p, p])


class ModeleClvFactice:
    def predict(self, X):
        return np.full(len(X), np.log1p(1000.0))


def resultats_factices(n: int = 40) -> pd.DataFrame:
    X = pd.DataFrame({"x": range(n)})
    return scorer_cycle(X, pd.Series([f"C{i}" for i in range(n)]), ModeleChurnFactice(),
                        ModeleClvFactice(), seuil_d9=0.5, capacite_d10=5)


class TestScorerCycle:
    def test_signalement_capacite_et_actions(self):
        resultats = resultats_factices()
        assert resultats["signale_D9"].sum() == (resultats["score_churn"] >= 0.5).sum()
        assert (resultats["priorite"] == "Haute").sum() == 5
        assert resultats["action_recommandee"].notna().all()


class TestJournal:
    def entree(self, tmp_path, cycle="2026-11", **kwargs):
        for nom in ("export.csv", "model.joblib", "model_clv.joblib"):
            (tmp_path / nom).write_bytes(nom.encode())
        return entree_journal(cycle, resultats_factices(), export=tmp_path / "export.csv",
                              modele_churn=tmp_path / "model.joblib", modele_clv=tmp_path / "model_clv.joblib",
                              gold_sha256="abc", seuil_d9=0.5, capacite_d10=5, **kwargs)

    def test_entree_trace_modele_export_et_regle_sans_donnee_par_compte(self, tmp_path):
        entree = self.entree(tmp_path, psi_max=0.31, variables_en_alerte=["csat"])
        assert entree["version_modele_churn"] == version_fichier(tmp_path / "model.joblib")
        assert len(entree["version_modele_churn"]) == 12
        assert entree["comptes_scores"] == 40 and entree["priorite_haute"] == 5
        assert entree["seuil_D9"] == 0.5 and entree["variables_en_alerte"] == ["csat"]
        assert "client_id" not in json.dumps(entree)

    def test_rejouer_un_cycle_remplace_son_entree(self, tmp_path):
        journal = tmp_path / "journal_scores.jsonl"
        assert lire_journal(journal) == []
        ajouter_au_journal(journal, self.entree(tmp_path, "2026-10"))
        ajouter_au_journal(journal, self.entree(tmp_path, "2026-11"))
        entrees = ajouter_au_journal(journal, self.entree(tmp_path, "2026-10"))
        assert [e["cycle"] for e in entrees] == ["2026-11", "2026-10"]
        assert lire_journal(journal) == entrees

    def test_purge_ne_garde_que_les_derniers_cycles(self, tmp_path):
        cycles = ["2026-08", "2026-09", "2026-10", "2026-11"]
        for cycle in cycles:
            (tmp_path / f"scores_{cycle}.parquet").write_bytes(b"x")
        purges = purger_scores(tmp_path, cycles, conserver=3)
        assert purges == ["2026-08"]
        assert sorted(p.stem for p in tmp_path.glob("*.parquet")) == [f"scores_{c}" for c in cycles[1:]]


def charger_exporteur():
    spec = importlib.util.spec_from_file_location("export_drift_metrics", RACINE / "scripts" / "export_drift_metrics.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestExporteurCycleCourant:
    def test_cycle_designe_ou_split_test_par_defaut(self, tmp_path):
        exporteur = charger_exporteur()
        gold = pd.DataFrame({"csat": [1.0, 2.0, 3.0], "split": ["train", "test", "test"]})
        assert exporteur.fenetre_courante(gold, "")["csat"].tolist() == [2.0, 3.0]
        chemin = tmp_path / "features.parquet"
        pd.DataFrame({"csat": [5.0]}).to_parquet(chemin)
        assert exporteur.fenetre_courante(gold, str(chemin))["csat"].tolist() == [5.0]
