"""Tests de `src/validation.py` : bornes physiques et types des entrées de l'API (lot 3, A3.2)."""
from pathlib import Path

import pandas as pd
import pytest

from src.features import FEATURES_V2, NUMERIQUES_V2
from src.validation import BORNES_PHYSIQUES, MAX_ERREURS, erreurs_valeur, valider_entrees


def test_une_borne_par_variable_numerique():
    assert set(BORNES_PHYSIQUES) == set(NUMERIQUES_V2)


def test_les_donnees_d_entrainement_passent_toutes():
    """Les bornes physiques ne doivent refuser aucune valeur du Gold v2 : elles visent
    l'impossible, pas l'inhabituel."""
    chemin = Path(__file__).resolve().parents[1] / "data" / "gold" / "clients_churn_gold_v2.parquet"
    if not chemin.exists():
        pytest.skip("Gold v2 absent (job de tests de la CI, sans dvc pull)")
    gold = pd.read_parquet(chemin)
    lignes = [(str(i), {k: (None if pd.isna(v) else v) for k, v in ligne.items()})
              for i, ligne in enumerate(gold[FEATURES_V2].to_dict(orient="records"))]
    assert valider_entrees(lignes, FEATURES_V2) == []


@pytest.mark.parametrize("variable, valeur, attendu", [
    ("csat", 5, None),
    ("csat", 0, "hors des bornes physiques [1 ; 5]"),
    ("retards_paiement_12m", 13, "hors des bornes physiques [0 ; 12]"),
    ("connexions_30j", -1, "hors des bornes physiques [0 ; +inf]"),
    ("connexions_30j", float("inf"), "nombre attendu"),
    ("connexions_30j", True, "nombre attendu"),
    ("connexions_30j", "12", "nombre attendu"),
    ("connexions_30j", None, None),
    ("plan", "Premium", None),          # modalité inconnue : acceptée, signalée par l'explication
    ("plan", 3, "texte attendu"),
    ("variable_hors_schema", 0.5, None),
])
def test_erreurs_valeur(variable, valeur, attendu):
    raison = erreurs_valeur(variable, valeur)
    assert raison == attendu if attendu is None else attendu in raison


def test_variable_inconnue_et_troncature():
    clients = [(f"CLI-{i}", {"csat": 9, "inconnue": 1}) for i in range(30)]
    erreurs = valider_entrees(clients, ["csat"])
    assert erreurs[0] == "CLI-0 : variable inconnue « inconnue »"
    assert erreurs[1].startswith("CLI-0 : csat : 9 hors des bornes")
    assert len(erreurs) == MAX_ERREURS + 1 and erreurs[-1] == "(liste tronquée)"
