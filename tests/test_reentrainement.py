"""Tests de `src/reentrainement.py` : challenger entraîné hors notebook, évaluation, journal.

Données synthétiques : un faux Gold v2 aux 20 variables, dont le churn dépend de trois
variables dans le sens attendu par la base de connaissance (connexion ancienne, peu
d'intégrations, faible ancienneté).
"""
import json

import numpy as np
import pandas as pd
import pytest

from src.evaluation import decider_promotion
from src.explain import charger_base_connaissance
from src.features import FEATURES_V2
from src.reentrainement import (
    FAMILLES, ajouter_decision, construire_challenger, decouper, entrainer, evaluer,
)


@pytest.fixture(scope="module")
def gold():
    rng = np.random.default_rng(0)
    n = 800
    g = pd.DataFrame({c: rng.normal(50, 10, n) for c in FEATURES_V2})
    g["secteur"] = rng.choice(["Tech", "Santé"], n)
    g["taille_entreprise"] = rng.choice(["PME", "GE"], n)
    g["plan"] = rng.choice(["Pro", "Starter"], n)
    g["derniere_connexion_jours"] = rng.integers(0, 120, n).astype(float)
    g["nb_integrations"] = rng.integers(0, 10, n).astype(float)
    g["anciennete_mois"] = rng.integers(1, 36, n).astype(float)
    logit = (0.03 * g["derniere_connexion_jours"] - 0.3 * g["nb_integrations"]
             - 0.06 * g["anciennete_mois"] + 0.5)
    g["churn"] = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    g["split"] = np.where(np.arange(n) < 600, "train", "test")
    return g


@pytest.fixture(scope="module")
def base():
    return charger_base_connaissance()


class TestConstruction:
    @pytest.mark.parametrize("famille", FAMILLES)
    def test_trois_familles(self, famille):
        assert construire_challenger(famille).named_steps["modele"] is not None

    def test_famille_inconnue(self):
        with pytest.raises(ValueError):
            construire_challenger("reseau_de_neurones")

    def test_decoupage(self, gold):
        X_train, y_train, X_test, y_test = decouper(gold)
        assert list(X_train.columns) == FEATURES_V2 and len(X_train) == 600 and len(X_test) == 200


class TestEntrainementEtEvaluation:
    def test_seuil_hors_pli_et_criteres(self, gold, base):
        X_train, y_train, X_test, y_test = decouper(gold)
        modele, seuil = entrainer(construire_challenger("logistique"), X_train, y_train)
        assert 0 < seuil < 1
        rapport = evaluer(modele, seuil, X_train, y_train, X_test, y_test, base)
        assert rapport["controles"] == "complets"
        assert rapport["metriques"]["pr_auc"] > rapport["metriques"]["taux_churn_observe"]   # mieux que le hasard
        assert [c["critere"][:2] for c in rapport["criteres"]] == ["D8", "D9", "Ca", "Ca", "Ba"]

    def test_controles_limites_pour_un_modele_non_lineaire(self, gold, base):
        X_train, y_train, X_test, y_test = decouper(gold)
        modele, seuil = entrainer(construire_challenger("boosting"), X_train, y_train)
        assert evaluer(modele, seuil, X_train, y_train, X_test, y_test, base)["controles"] == \
            "exclusions et couverture seulement"

    def test_reentrainement_a_l_identique_conserve_le_champion(self, gold, base):
        X_train, y_train, X_test, y_test = decouper(gold)
        champion, seuil = entrainer(construire_challenger("logistique"), X_train, y_train)
        challenger, seuil_bis = entrainer(construire_challenger("logistique"), X_train, y_train)
        a = evaluer(champion, seuil, X_train, y_train, X_test, y_test, base)
        b = evaluer(challenger, seuil_bis, X_train, y_train, X_test, y_test, base)
        assert seuil == seuil_bis and a["metriques"] == b["metriques"]
        decision = decider_promotion(b["criteres"], b["metriques"], a["metriques"])
        assert decision["criteres"][-1]["valeur"] == 0.0          # même PR-AUC : aucun gain
        assert decision["decision"] != "promouvable"


def test_journal_des_decisions_en_ajout(tmp_path):
    journal = tmp_path / "reentrainement" / "journal_decisions.jsonl"
    ajouter_decision(journal, {"declencheur": "calendrier", "decision": "champion_conserve"})
    ajouter_decision(journal, {"declencheur": "derive_top5", "decision": "refuse"})
    lignes = [json.loads(ligne) for ligne in journal.read_text(encoding="utf-8").splitlines()]
    assert [ligne["decision"] for ligne in lignes] == ["champion_conserve", "refuse"]
    assert all("horodatage_utc" in ligne for ligne in lignes)
