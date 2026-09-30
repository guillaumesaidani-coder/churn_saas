"""Tests unitaires de `src/explain.py` : décomposition exacte du score, explication en langage
métier, trace de la décision, contrôles par la base de connaissance.

Données utilisées : jamais le Gold réel ni les `.joblib` -- un pipeline de même structure que
le modèle du projet (one-hot + imputation médiane + standardisation + régression logistique),
entraîné sur des données synthétiques dont on connaît le sens des effets. Seul le dernier groupe
de tests lit la vraie base de connaissance, pour vérifier sa cohérence avec `src/features.py`.
"""
import numpy as np
import pandas as pd
import pytest
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.explain import (
    attribuer_derive,
    charger_base_connaissance,
    contributions,
    controler_concentration,
    controler_couverture,
    controler_exclusions,
    controler_modalites,
    controler_modele,
    controler_sens,
    effets_lineaires,
    expliquer_batch,
    expliquer_compte,
    expliquer_decision,
    parts_explication,
    reference_explication,
)
from src.features import FEATURES_V2, LEURRES, REDONDANTES_CATALOGUE
from src.scoring import assigner_priorites

BASE = {
    "variables": {
        "plan": {"libelle": "Formule", "type": "categorielle", "modalites": ["Starter", "Pro"],
                 "sens_attendu": "indetermine"},
        "derniere_connexion_jours": {"libelle": "Jours depuis la dernière connexion", "type": "numerique",
                                     "unite": "j", "decimales": 0, "plage": [0, 200], "sens_attendu": "hausse"},
        "nb_integrations": {"libelle": "Intégrations", "type": "numerique", "unite": "intégrations",
                            "decimales": 0, "plage": [0, 16], "sens_attendu": "baisse"},
    },
    "exclusions": {
        "sante_compte_fin_periode": {"categorie": "fuite", "raison": "Calculée après la décision."},
        "prix_mensuel_par_siege_eur": {"categorie": "redondante", "raison": "Une valeur par plan."},
    },
    "controles": {
        "gravite_exclusion": {"fuite": "bloquant", "redondante": "avertissement"},
        "gravite_sens_contraire": "avertissement",
        "part_max_une_variable": 0.5,
        "gravite_concentration": "bloquant",
    },
}
FEATURES = ["plan", "derniere_connexion_jours", "nb_integrations"]


def _pipeline(categorielles, numeriques, estimateur=None):
    return Pipeline([
        ("preparation", ColumnTransformer([
            ("cat", OneHotEncoder(handle_unknown="ignore"), categorielles),
            ("num", Pipeline([("imputation", SimpleImputer(strategy="median")),
                              ("standardisation", StandardScaler())]), numeriques),
        ])),
        ("modele", estimateur if estimateur is not None else LogisticRegression(max_iter=1000)),
    ])


@pytest.fixture(scope="module")
def donnees():
    """Risque croissant avec la récence de connexion, décroissant avec les intégrations."""
    rng = np.random.default_rng(0)
    n = 600
    X = pd.DataFrame({
        "plan": rng.choice(["Starter", "Pro"], n),
        "derniere_connexion_jours": rng.integers(0, 120, n).astype(float),
        "nb_integrations": rng.integers(0, 10, n).astype(float),
    })
    logit = 0.04 * X["derniere_connexion_jours"] - 0.5 * X["nb_integrations"] + 0.5 * (X["plan"] == "Starter")
    y = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    X.loc[::17, "nb_integrations"] = np.nan   # valeurs manquantes, imputées par le pipeline
    return X, y


@pytest.fixture(scope="module")
def modele(donnees):
    X, y = donnees
    return _pipeline(["plan"], ["derniere_connexion_jours", "nb_integrations"]).fit(X, y)


@pytest.fixture(scope="module")
def reference(modele, donnees):
    return reference_explication(modele, donnees[0])


class TestDecompositionExacte:
    def test_reference_plus_contributions_egale_le_logit(self, modele, reference, donnees):
        X = donnees[0]
        contrib = contributions(modele, X, reference)
        np.testing.assert_allclose(reference["logit_reference"] + contrib.sum(axis=1),
                                   modele.decision_function(X), atol=1e-9)

    def test_exacte_aussi_pour_manquant_et_modalite_inconnue(self, modele, reference):
        X = pd.DataFrame({"plan": ["Premium", None], "derniere_connexion_jours": [np.nan, 300.0],
                          "nb_integrations": [2.0, np.nan]})
        contrib = contributions(modele, X, reference)
        np.testing.assert_allclose(reference["logit_reference"] + contrib.sum(axis=1),
                                   modele.decision_function(X), atol=1e-9)

    def test_une_colonne_par_variable_d_origine(self, modele, reference, donnees):
        contrib = contributions(modele, donnees[0].head(3), reference)
        assert list(contrib.columns) == FEATURES   # les deux colonnes one-hot de `plan` sont regroupées

    def test_contributions_nulles_en_moyenne_sur_la_reference(self, modele, reference, donnees):
        contrib = contributions(modele, donnees[0], reference)
        np.testing.assert_allclose(contrib.mean(), 0, atol=1e-9)

    def test_modele_non_lineaire_refuse(self, donnees):
        X, y = donnees
        foret = _pipeline(["plan"], ["derniere_connexion_jours", "nb_integrations"],
                          RandomForestClassifier(n_estimators=5, random_state=0)).fit(X, y)
        with pytest.raises(TypeError):
            reference_explication(foret, X)

    def test_reference_d_un_autre_modele_refusee(self, donnees, reference):
        X, y = donnees
        autre = _pipeline([], ["derniere_connexion_jours", "nb_integrations"]).fit(X, y)
        with pytest.raises(ValueError):
            contributions(autre, X, reference)


class TestExplicationDUnCompte:
    def test_facteurs_dans_le_bon_sens_avec_libelles(self, modele, reference):
        x = pd.Series({"plan": "Pro", "derniere_connexion_jours": 110.0, "nb_integrations": 9.0})
        contrib = contributions(modele, x.to_frame().T, reference).iloc[0]

        explication = expliquer_compte(x, contrib, reference, BASE)

        hausse = [f["variable"] for f in explication["facteurs_hausse"]]
        baisse = [f["variable"] for f in explication["facteurs_baisse"]]
        assert "derniere_connexion_jours" in hausse and "nb_integrations" in baisse
        texte = explication["facteurs_hausse"][0]["texte"]
        assert texte.startswith("Jours depuis la dernière connexion : 110 j (moyenne")
        assert texte.endswith("augmente le risque")

    def test_avertissements_manquant_hors_plage_modalite_inconnue(self, modele, reference):
        x = pd.Series({"plan": "Premium", "derniere_connexion_jours": 300.0, "nb_integrations": np.nan})
        contrib = contributions(modele, x.to_frame().T, reference).iloc[0]

        avertissements = " | ".join(expliquer_compte(x, contrib, reference, BASE)["avertissements"])

        assert "Formule : modalité « Premium » inconnue du modèle" in avertissements
        assert "hors de la plage du dictionnaire [0 j ; 200 j]" in avertissements
        assert "Intégrations : valeur manquante, remplacée par la médiane d'entraînement" in avertissements


class TestExplicationDeLaDecision:
    @pytest.fixture
    def priorites(self):
        resultats = pd.DataFrame({"client_id": ["A", "B", "C"], "score_churn": [0.9, 0.8, 0.1],
                                  "perte_attendue_eur": [100.0, 5000.0, 50.0]})
        return assigner_priorites(resultats, seuil_d9=0.5, capacite_haute=1).set_index("client_id")

    def test_trois_priorites(self, priorites):
        textes = {cid: expliquer_decision(ligne, 0.5, 1, nb_signales=2) for cid, ligne in priorites.iterrows()}
        assert textes["B"].startswith("Priorité Haute") and "rang 1 sur 2 comptes signalés" in textes["B"]
        assert textes["A"].startswith("Priorité Moyenne") and "au-delà de la capacité de 1" in textes["A"]
        assert textes["C"] == "Priorité Basse : probabilité de churn 0,100, sous le seuil de signalement D9 (0,5000)."

    def test_expliquer_batch_un_resultat_par_compte(self, modele, reference, donnees):
        X = donnees[0].head(5)
        resultats = pd.DataFrame({"client_id": list("abcde"), "score_churn": modele.predict_proba(X)[:, 1].round(3),
                                  "perte_attendue_eur": [10.0, 20.0, 30.0, 40.0, 50.0]})
        resultats = assigner_priorites(resultats, seuil_d9=0.5, capacite_haute=1)

        explications = expliquer_batch(modele, X, resultats, reference, BASE, seuil_d9=0.5, capacite_haute=1)

        assert len(explications) == 5
        assert all(e["decision"].startswith(f"Priorité {p}") for e, p in zip(explications, resultats["priorite"]))


class TestControles:
    def test_variable_exclue_bloquante_ou_avertissement_selon_categorie(self):
        anomalies = {a["variable"]: a["gravite"]
                     for a in controler_exclusions(["sante_compte_fin_periode", "prix_mensuel_par_siege_eur", "plan"], BASE)}
        assert anomalies == {"sante_compte_fin_periode": "bloquant", "prix_mensuel_par_siege_eur": "avertissement"}

    def test_variable_absente_de_la_base(self):
        assert [a["variable"] for a in controler_couverture(["plan", "variable_mystere"], BASE)] == ["variable_mystere"]

    def test_sens_contraire_signale_indetermine_ignore(self):
        anomalies = controler_sens({"derniere_connexion_jours": -0.3, "nb_integrations": -0.5, "plan": 1.0}, BASE)
        assert [(a["variable"], a["gravite"]) for a in anomalies] == [("derniere_connexion_jours", "avertissement")]

    def test_sens_appris_conforme_sur_donnees_synthetiques(self, modele, reference):
        effets = effets_lineaires(modele, reference)
        assert effets["derniere_connexion_jours"] > 0 > effets["nb_integrations"]
        assert controler_sens(effets, BASE) == []

    def test_concentration(self):
        parts = pd.Series({"a": 0.7, "b": 0.3})
        assert [a["variable"] for a in controler_concentration(parts, BASE)] == ["a"]
        assert controler_concentration(pd.Series({"a": 0.4, "b": 0.35, "c": 0.25}), BASE) == []

    def test_modalites_hors_dictionnaire(self):
        reference = {"modalites_apprises": {"plan": ["Pro", "Starter", "starter "]}}
        anomalies = controler_modalites(reference, BASE)
        assert anomalies[0]["gravite"] == "avertissement" and "starter " in anomalies[0]["constat"]

    def test_modele_avec_fuite_detecte_deux_fois(self, donnees):
        """Une variable qui recopie presque la cible : exclue par la base ET concentrée."""
        X, y = donnees
        X = X.assign(sante_compte_fin_periode=y * 100 + np.random.default_rng(1).normal(0, 5, len(y)))
        numeriques = ["derniere_connexion_jours", "nb_integrations", "sante_compte_fin_periode"]
        fuite = _pipeline(["plan"], numeriques).fit(X, y)
        ref = reference_explication(fuite, X)

        table = controler_modele(list(X.columns), BASE, fuite, ref, X)

        bloquants = table[table["gravite"] == "bloquant"]
        assert set(bloquants["controle"]) == {"exclusion", "concentration"}
        assert set(bloquants["variable"]) == {"sante_compte_fin_periode"}
        assert table["gravite"].iloc[0] == "bloquant"   # trié du plus grave au moins grave

    def test_modele_conforme_aucun_bloquant(self, modele, reference, donnees):
        table = controler_modele(FEATURES, BASE, modele, reference, donnees[0])
        assert (table["gravite"] != "bloquant").all()


class TestAttributionDeDerive:
    def test_somme_des_ecarts_egale_ecart_de_logit_moyen(self, modele, reference, donnees):
        X = donnees[0]
        derive = X.assign(derniere_connexion_jours=X["derniere_connexion_jours"] + 30)
        table = attribuer_derive(contributions(modele, X, reference), contributions(modele, derive, reference))

        ecart_logit = modele.decision_function(derive).mean() - modele.decision_function(X).mean()
        assert table["ecart"].sum() == pytest.approx(ecart_logit)
        assert table.index[0] == "derniere_connexion_jours"   # la seule variable modifiée
        assert table.loc["nb_integrations", "ecart"] == pytest.approx(0)

    def test_parts_normalisees(self, modele, reference, donnees):
        parts = parts_explication(contributions(modele, donnees[0], reference))
        assert parts.sum() == pytest.approx(1) and parts.is_monotonic_decreasing


@pytest.fixture(scope="module")
def base():
    return charger_base_connaissance()


class TestBaseDeConnaissanceDuProjet:
    """La vraie base (`knowledge/base_connaissance.yaml`) doit rester cohérente avec le code."""

    def test_decrit_exactement_les_features_du_modele(self, base):
        assert set(base["variables"]) == set(FEATURES_V2)

    def test_exclusions_couvrent_leurres_redondances_fuite_et_cibles(self, base):
        attendues = set(LEURRES) | set(REDONDANTES_CATALOGUE) | {
            "sante_compte_fin_periode", "valeur_vie_client_eur", "client_id", "commentaire_csm", "churn"}
        assert attendues <= set(base["exclusions"])
        assert set(base["exclusions"]).isdisjoint(FEATURES_V2)

    def test_chaque_categorie_d_exclusion_a_une_gravite(self, base):
        categories = {e["categorie"] for e in base["exclusions"].values()}
        assert categories <= set(base["controles"]["gravite_exclusion"])

    def test_fiches_completes(self, base):
        for nom, fiche in base["variables"].items():
            assert fiche["libelle"] and fiche["sens_attendu"] in {"hausse", "baisse", "indetermine"}, nom
            if fiche["type"] == "numerique":
                bas, haut = fiche["plage"]
                assert bas < haut, nom
            else:
                assert fiche["modalites"], nom

    def test_modele_v2_ne_contient_aucune_variable_bloquante(self, base):
        assert [a for a in controler_exclusions(FEATURES_V2, base) if a["gravite"] == "bloquant"] == []
