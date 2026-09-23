"""Tests unitaires de `src/scoring.py` (logique de `notebooks/06_implementation_scoring.ipynb`
§1-§3, réalignée sur la règle de décision D9/D10/D14 réellement exécutée dans le notebook).

Données utilisées : jamais le jeu Gold réel ni les artefacts `.joblib` -- uniquement des
DataFrames synthétiques minimaux et des modèles factices (`FakeModelChurn`/`FakeModelCLV`)
dont les sorties sont fixées à l'avance, pour pouvoir calculer l'attendu à la main.
"""
import numpy as np
import pandas as pd
import pytest

from src.scoring import (
    action_est_conforme_d3,
    assigner_priorites,
    calibrer_seuil_d9,
    recommander_action,
    scorer_batch,
)


class FakeModelChurn:
    """Modèle factice : renvoie des probabilités de churn fixées à l'avance."""

    def __init__(self, probas):
        self.probas = np.asarray(probas, dtype=float)

    def predict_proba(self, X):
        return np.column_stack([1 - self.probas, self.probas])


class FakeModelCLV:
    """Modèle factice : renvoie des prédictions en espace log1p (comme le vrai modèle CLV),
    pour que `np.expm1` dans `scorer_batch` les ramène à des CLV en euros connues à l'avance."""

    def __init__(self, predictions_log_space):
        self.predictions_log_space = np.asarray(predictions_log_space, dtype=float)

    def predict(self, X):
        return self.predictions_log_space


def _X(n):
    # Contenu sans importance : les modèles factices ignorent X, seule sa longueur compte.
    return pd.DataFrame({"feature_neutre": [0] * n})


class TestScorerBatch:
    def test_calcul_exact_de_la_perte_attendue(self):
        client_ids = pd.Series(["CLI-1", "CLI-2", "CLI-3"])
        model_churn = FakeModelChurn([0.5, 0.2, 0.9])
        model_clv = FakeModelCLV(np.log1p([1000, 500, 2000]))

        resultat = scorer_batch(_X(3), client_ids, model_churn, model_clv)

        assert resultat["client_id"].tolist() == ["CLI-1", "CLI-2", "CLI-3"]
        assert resultat["score_churn"].tolist() == [0.5, 0.2, 0.9]
        assert resultat["valeur_vie_estimee_eur"].tolist() == [1000.0, 500.0, 2000.0]
        # perte_attendue = score_churn x valeur_vie_estimee (D14)
        assert resultat["perte_attendue_eur"].tolist() == [500.0, 100.0, 1800.0]

    def test_clv_negative_est_clippee_a_zero(self):
        # expm1 d'une prédiction très négative est négatif : ne doit jamais sortir en CLV négative
        model_churn = FakeModelChurn([0.5])
        model_clv = FakeModelCLV([-5.0])

        resultat = scorer_batch(_X(1), pd.Series(["CLI-1"]), model_churn, model_clv)

        assert resultat.loc[0, "valeur_vie_estimee_eur"] == 0.0
        assert resultat.loc[0, "perte_attendue_eur"] == 0.0

    def test_ordre_des_lignes_preserve(self):
        model_churn = FakeModelChurn([0.1, 0.9, 0.5])
        model_clv = FakeModelCLV(np.log1p([100, 100, 100]))

        resultat = scorer_batch(_X(3), pd.Series(["A", "B", "C"]), model_churn, model_clv)

        assert resultat["client_id"].tolist() == ["A", "B", "C"]


class TestCalibrerSeuilD9:
    def test_seuil_le_plus_haut_qui_garantit_le_rappel_cible(self):
        y_true = np.array([1, 1, 1, 1, 0, 0, 0, 0, 0, 0])
        # Les 4 positifs ont les scores les plus hauts -- seuil = score du 4e positif garantit rappel=1.0
        score = np.array([0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.05])

        seuil = calibrer_seuil_d9(y_true, score, rappel_cible=1.0)

        assert seuil == pytest.approx(0.6)

    def test_rappel_cible_plus_permissif_donne_un_seuil_plus_haut(self):
        y_true = np.array([1, 1, 1, 1, 0, 0, 0, 0, 0, 0])
        score = np.array([0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.05])

        seuil_rappel_100 = calibrer_seuil_d9(y_true, score, rappel_cible=1.0)
        seuil_rappel_50 = calibrer_seuil_d9(y_true, score, rappel_cible=0.5)

        assert seuil_rappel_50 >= seuil_rappel_100


class TestAssignerPriorites:
    def test_capacite_haute_plafonne_les_comptes_signales_les_plus_prioritaires(self):
        resultats = pd.DataFrame({
            "client_id": ["A", "B", "C", "D"],
            "score_churn": [0.9, 0.8, 0.7, 0.1],  # D en dessous du seuil D9
            "perte_attendue_eur": [100, 500, 300, 50],
        })

        out = assigner_priorites(resultats, seuil_d9=0.5, capacite_haute=2)

        assert out.set_index("client_id")["priorite"].to_dict() == {
            "A": "Moyenne",  # signalé, perte 100 -- hors capacité (B et C plus prioritaires)
            "B": "Haute",    # signalé, perte 500 -- 1er
            "C": "Haute",    # signalé, perte 300 -- 2e (capacité = 2)
            "D": "Basse",    # non signalé (score < seuil)
        }

    def test_action_recommandee_correspond_a_la_priorite(self):
        resultats = pd.DataFrame({
            "client_id": ["A"], "score_churn": [0.9], "perte_attendue_eur": [100],
        })

        out = assigner_priorites(resultats, seuil_d9=0.5, capacite_haute=10)

        assert out.loc[0, "action_recommandee"] == recommander_action("Haute")


class TestRecommanderAction:
    @pytest.mark.parametrize("priorite", ["Haute", "Moyenne", "Basse"])
    def test_mapping_connu(self, priorite):
        action = recommander_action(priorite)
        assert isinstance(action, str) and action

    def test_priorite_inconnue_leve_une_erreur(self):
        with pytest.raises(KeyError):
            recommander_action("Critique")


class TestConformiteD3:
    """D3 / art. 22 RGPD (NB06 §3) : jamais d'action automatique sans validation humaine."""

    @pytest.mark.parametrize("priorite", ["Haute", "Moyenne", "Basse"])
    def test_actions_reelles_sont_conformes(self, priorite):
        assert action_est_conforme_d3(recommander_action(priorite))

    @pytest.mark.parametrize(
        "action_a_risque",
        [
            "Résiliation appliquée automatiquement, sans validation du CSM",
            "Downgrade appliqué directement sur le compte",
            "Ajustement tarifaire automatiquement exécuté sans intervention humaine",
        ],
    )
    def test_formulation_automatique_est_rejetee(self, action_a_risque):
        assert not action_est_conforme_d3(action_a_risque)
