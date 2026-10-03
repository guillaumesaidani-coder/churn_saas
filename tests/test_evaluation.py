"""Tests de `src/evaluation.py` : métriques, critères de promotion, déclencheurs de ré-entraînement.

Données synthétiques uniquement : des probabilités et des étiquettes fixées à la main.
"""
import numpy as np
import pandas as pd
import pytest

from src.evaluation import (
    GAIN_PR_AUC_PROMOTION, criteres_modele, criteres_reproduction, declencheurs_cycle, decider_promotion,
    metriques_classification, score_regle_metier, top_importance,
)

AUCUN_CONTROLE = pd.DataFrame(columns=["controle", "variable", "gravite", "constat"])


def metriques(**valeurs):
    """Métriques d'un bon modèle, modifiables champ par champ."""
    m = {"pr_auc": 0.75, "roc_auc": 0.88, "pr_auc_baseline_metier_D8": 0.59, "gain_pr_auc_vs_D8": 0.16,
         "rappel_seuil_D9": 0.82, "brier": 0.12, "brier_reference": 0.20,
         "probabilite_moyenne": 0.28, "taux_churn_observe": 0.28}
    return {**m, **valeurs}


class TestMetriques:
    def test_classement_parfait(self):
        y = pd.Series([0, 0, 1, 1])
        proba = np.array([0.1, 0.2, 0.8, 0.9])
        m = metriques_classification(y, proba, score_regle=pd.Series([0.0, 1.0, 0.0, 1.0]), seuil_d9=0.5,
                                     taux_reference=0.5)
        assert m["pr_auc"] == 1.0 and m["roc_auc"] == 1.0 and m["rappel_seuil_D9"] == 1.0
        assert m["gain_pr_auc_vs_D8"] == pytest.approx(m["pr_auc"] - m["pr_auc_baseline_metier_D8"], abs=1e-4)
        assert m["brier"] < m["brier_reference"] == 0.25

    def test_regle_metier_d8(self):
        X = pd.DataFrame({"anciennete_mois": [36, 1], "nb_integrations": [np.nan, 0.0],
                          "derniere_connexion_jours": [0, 200]})
        score = score_regle_metier(X, mediane_integrations=16)
        assert score.tolist() == pytest.approx([-2.0, 1 - 1 / 36])   # ancien et intégré vs récent et inactif


class TestCriteres:
    def test_bon_modele_tient_tous_ses_criteres(self):
        assert all(c["respecte"] for c in criteres_modele(metriques(), AUCUN_CONTROLE))

    @pytest.mark.parametrize("champ, valeur, critere", [
        ("gain_pr_auc_vs_D8", 0.12, "D8"),
        ("rappel_seuil_D9", 0.78, "D9"),
        ("brier", 0.25, "Brier"),
        ("probabilite_moyenne", 0.40, "probabilité moyenne"),
    ])
    def test_un_critere_non_tenu(self, champ, valeur, critere):
        echecs = [c["critere"] for c in criteres_modele(metriques(**{champ: valeur}), AUCUN_CONTROLE) if not c["respecte"]]
        assert len(echecs) == 1 and critere in echecs[0]

    def test_controle_bloquant(self):
        controles = pd.DataFrame([{"controle": "exclusion", "variable": "x", "gravite": "bloquant", "constat": ""}])
        echecs = [c["critere"] for c in criteres_modele(metriques(), controles) if not c["respecte"]]
        assert echecs == ["Base de connaissance : aucun contrôle bloquant"]

    def test_reproduction_des_metriques_publiees(self):
        publiees = {"pr_auc": 0.75, "roc_auc": 0.88, "rappel_seuil_D9": 0.82, "pr_auc_baseline_metier_D8": 0.59}
        assert all(c["respecte"] for c in criteres_reproduction(metriques(pr_auc=0.751), publiees))
        assert not all(c["respecte"] for c in criteres_reproduction(metriques(pr_auc=0.74), publiees))


class TestDecisionDePromotion:
    def decision(self, m_challenger, m_champion=None):
        return decider_promotion(criteres_modele(m_challenger, AUCUN_CONTROLE), m_challenger, m_champion or metriques())

    def test_refuse_si_un_critere_manque(self):
        d = self.decision(metriques(pr_auc=0.80, rappel_seuil_D9=0.70))
        assert d["decision"] == "refuse" and "D9" in d["motif"]

    def test_refuse_si_moins_bon_que_le_modele_en_service(self):
        d = self.decision(metriques(pr_auc=0.74))
        assert d["decision"] == "refuse" and "modèle en service" in d["motif"]

    def test_champion_conserve_sans_gain_suffisant(self):
        assert self.decision(metriques())["decision"] == "champion_conserve"
        assert self.decision(metriques(pr_auc=0.75 + GAIN_PR_AUC_PROMOTION / 2))["decision"] == "champion_conserve"

    def test_promouvable_si_meilleur(self):
        d = self.decision(metriques(pr_auc=0.77))
        assert d["decision"] == "promouvable" and "décider" in d["motif"]
        assert d["criteres"][-1]["critere"] == "PR-AUC au moins égale au modèle en service"


class TestDeclencheurs:
    def test_derive_seulement_sur_le_top_5(self):
        psi = pd.Series({"csat": 0.9, "heures_usage_30j": 0.9, "anciennete_mois": 0.01})
        d = {x["declencheur"]: x for x in declencheurs_cycle(psi, ["csat", "anciennete_mois"], 0.36, 0.366)}
        assert d["derive_top5"]["actif"] and d["derive_top5"]["detail"] == ["csat"]
        assert not d["volume_signales"]["actif"]
        assert "rappel_reel" not in d                       # connu seulement au rapprochement

    def test_volume_et_rappel_reel(self):
        d = {x["declencheur"]: x for x in declencheurs_cycle(pd.Series(dtype=float), [], 0.80, 0.366, rappel_reel=0.70)}
        assert d["volume_signales"]["actif"] and d["volume_signales"]["detail"] == pytest.approx(2.19, abs=0.01)
        assert d["rappel_reel"]["actif"] and not d["derive_top5"]["actif"]

    def test_top_importance(self):
        parts = pd.Series({"a": 0.1, "b": 0.4, "c": 0.3, "d": 0.2})
        assert top_importance(parts, n=2) == ["b", "c"]
