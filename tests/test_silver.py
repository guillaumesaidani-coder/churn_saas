"""Tests unitaires de `src/silver.py` (logique de `notebooks/02_nettoyage_silver.ipynb` §1-§6).

Données utilisées : uniquement des DataFrames synthétiques minimaux -- jamais le parquet
Bronze réel -- pour isoler chaque règle de nettoyage (dédoublonnage, dates, nombres,
catégorielles, jointure, valeurs manquantes) de la donnée métier réelle.
"""
import numpy as np
import pandas as pd
import pytest

from src.silver import (
    NUMERIC_COLUMNS,
    clean_silver,
    drop_strict_duplicates,
    normalize_secteur,
    parse_date_multi,
    parse_numeric_fr,
)


class TestDropStrictDuplicates:
    def test_deux_lignes_identiques_sur_les_colonnes_metier_sont_fusionnees(self):
        clients = pd.DataFrame({
            "_source_file": ["a.csv", "a.csv"],
            "_ingested_at_utc": ["t0", "t1"],  # diffère, mais ignoré (colonne technique)
            "client_id": ["CLI-1", "CLI-1"],
            "plan": ["Pro", "Pro"],
        })

        out, n_doublons = drop_strict_duplicates(clients)

        assert n_doublons == 1
        assert len(out) == 1

    def test_lignes_differentes_sur_une_colonne_metier_sont_conservees(self):
        clients = pd.DataFrame({
            "_source_file": ["a.csv", "a.csv"],
            "_ingested_at_utc": ["t0", "t0"],
            "client_id": ["CLI-1", "CLI-2"],
            "plan": ["Pro", "Basic"],
        })

        out, n_doublons = drop_strict_duplicates(clients)

        assert n_doublons == 0
        assert len(out) == 2


class TestParseDateMulti:
    @pytest.mark.parametrize(
        "valeur, attendu",
        [
            ("2025-06-01", "2025-06-01"),
            ("01/06/2025", "2025-06-01"),
            ("01 Jun 2025", "2025-06-01"),
        ],
    )
    def test_chacun_des_trois_formats_est_reconnu(self, valeur, attendu):
        result = parse_date_multi(pd.Series([valeur]))

        assert result.iloc[0] == pd.Timestamp(attendu)

    def test_format_inconnu_devient_nat(self):
        result = parse_date_multi(pd.Series(["31 Février 2025"]))

        assert pd.isna(result.iloc[0])


class TestParseNumericFr:
    @pytest.mark.parametrize(
        "valeur, attendu",
        [
            ("33,3", 33.3),
            ("20.0%", 20.0),
            ("0.5 h", 0.5),
            ("280.62 €", 280.62),
            ("42", 42.0),
        ],
    )
    def test_nettoie_virgule_pourcentage_euro_et_heure(self, valeur, attendu):
        result = parse_numeric_fr(pd.Series([valeur]))

        assert result.iloc[0] == pytest.approx(attendu)

    def test_chaine_vide_devient_nan_pas_zero(self):
        result = parse_numeric_fr(pd.Series([""]))

        assert pd.isna(result.iloc[0])


class TestNormalizeSecteur:
    @pytest.mark.parametrize(
        "valeur, attendu",
        [
            ("technologie", "Tech"),
            ("FINANCE", "Finance"),
            ("e-Commerce", "Commerce"),
            ("Santé publique", "Santé"),
        ],
    )
    def test_sous_chaine_stable_reconnue_quelle_que_soit_la_casse(self, valeur, attendu):
        assert normalize_secteur(valeur) == attendu

    def test_chaine_vide_devient_nan(self):
        assert pd.isna(normalize_secteur(""))

    def test_valeur_inattendue_est_laissee_telle_quelle(self):
        assert normalize_secteur("Aéronautique") == "Aéronautique"


def _clients_bronze_minimal() -> pd.DataFrame:
    base = {
        "_source_file": "churn_saas_complet.csv",
        "_ingested_at_utc": "2026-01-01T00:00:00+00:00",
        "date_souscription": "2025-06-01",
        "plan": "  pro ",
        "taille_entreprise": " pme ",
        "pays": "France",
        "secteur": "technologie",
        "anciennete_mois": "12",
        "sieges_souscrits": "10",
        "utilisateurs_actifs": "8",
        "taux_adoption_pct": "80%",
        "connexions_30j": "20",
        "heures_usage_30j": "40",
        "fonctionnalites_total": "10",
        "fonctionnalites_utilisees": "5",
        "nb_integrations": "2",
        "derniere_connexion_jours": "1",
        "tickets_support_90j": "0",
        "delai_reponse_support_h": "2 h",
        "csat": "4",
        "retards_paiement_12m": "0",
        "revenu_mensuel_recurrent_eur": "990,0",
        "sante_compte_fin_periode": "0,8",
        "valeur_vie_client_eur": "1000",
        "churn": "0",
    }
    ligne_2 = dict(base, revenu_mensuel_recurrent_eur="", secteur="", pays="")
    return pd.DataFrame([base, ligne_2])


def _catalogue_bronze_minimal() -> pd.DataFrame:
    return pd.DataFrame([{
        "plan": "Pro",
        "prix_mensuel_par_siege_eur": "99",
        "fonctionnalites_incluses": "10",
        "sla_reponse_h": "4",
        "quota_stockage_go": "100",
        "support_dedie": "true",
    }])


class TestCleanSilverIntegration:
    def test_pipeline_complet_sur_un_cas_minimal(self):
        clients = _clients_bronze_minimal()
        catalogue = _catalogue_bronze_minimal()

        out, report = clean_silver(clients, catalogue)

        assert "_source_file" not in out.columns
        assert "_ingested_at_utc" not in out.columns
        assert report["n_orphelins_catalogue"] == 0
        # MRR manquant recalculé via sieges_souscrits (10) x prix catalogue (99)
        assert out.loc[out["revenu_mensuel_recurrent_eur"] == 990.0, "revenu_mensuel_recurrent_eur"].tolist() == [990.0, 990.0]
        assert out["secteur"].tolist() == ["Tech", "Inconnu"]
        assert out["pays"].tolist() == ["France", "Inconnu"]
        assert report["n_secteur_manquant"] == 1
        assert report["n_pays_manquant"] == 1

    def test_colonne_numerique_hors_liste_mediane_sans_nan_nest_pas_modifiee(self):
        clients = _clients_bronze_minimal()
        catalogue = _catalogue_bronze_minimal()

        out, _ = clean_silver(clients, catalogue)

        assert out["anciennete_mois"].tolist() == [12.0, 12.0]

    def test_impute_medians_false_laisse_les_nan_pour_le_pipeline(self):
        clients = _clients_bronze_minimal()
        clients.loc[1, "csat"] = ""
        catalogue = _catalogue_bronze_minimal()

        avec, rapport_avec = clean_silver(clients, catalogue)
        sans, rapport_sans = clean_silver(clients, catalogue, impute_medians=False)

        assert avec["csat"].isna().sum() == 0
        assert sans["csat"].isna().sum() == 1
        assert rapport_sans["medianes"] == {}
        assert "csat" in rapport_avec["medianes"]
