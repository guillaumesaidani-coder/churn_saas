#!/usr/bin/env python
"""Expose en métriques Prometheus la dérive entre le Gold dataset de référence (split
`train`, figé au moment de l'entraînement du modèle en production) et le cycle courant
(split `test`, qui tient lieu de "prochain cycle mensuel" en l'absence d'un nouvel export
CRM réel -- voir `notebooks/06_implementation_scoring.ipynb` §0, même convention).

Recalcule (`src.drift.drift_table`) à chaque relecture plutôt que de relire un CSV déjà
produit (contrairement à `py-init/ml/scripts/export_drift_metrics.py`, qui republie un
calcul déjà fait ailleurs) : ici, aucun script batch de calcul de dérive séparé n'existe
encore -- ce script est la seule source du calcul, pas seulement de son exposition.

Port 9110 (même convention que py-init/ml : le 9109 y était déjà occupé par un autre
exporteur -- non applicable ici, mais gardé pour cohérence entre les deux projets).

Usage : python scripts/export_drift_metrics.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pandas as pd
from prometheus_client import Gauge, start_http_server

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.drift import drift_table  # noqa: E402

GOLD_DIR = Path(os.getenv("GOLD_DIR", "data/gold"))
PORT = int(os.getenv("DRIFT_EXPORTER_PORT", "9110"))
REFRESH_SECONDS = int(os.getenv("DRIFT_REFRESH_SECONDS", "60"))
PSI_ALERT_THRESHOLD = 0.25

drift_psi = Gauge("churn_saas_drift_psi", "PSI par feature (référence = split train)", ["feature"])
drift_ks_pvalue = Gauge("churn_saas_drift_ks_pvalue", "p-value KS par feature", ["feature"])
drift_alerte = Gauge("churn_saas_drift_alerte", "1 si PSI > seuil, 0 sinon", ["feature"])


def numeric_feature_columns(gold: pd.DataFrame, feature_columns: list[str]) -> list[str]:
    return [c for c in feature_columns if pd.api.types.is_numeric_dtype(gold[c])]


def _reload() -> int:
    """Relit le Gold dataset, recalcule la table de dérive, met à jour les gauges.
    Retourne le nombre de features suivies (0 si le Gold dataset n'est pas encore disponible)."""
    gold_path = GOLD_DIR / "clients_churn_gold.parquet"
    manifest_path = GOLD_DIR / "gold_manifest.json"
    if not gold_path.exists() or not manifest_path.exists():
        return 0

    import json
    with open(manifest_path, "r", encoding="utf-8") as f:
        feature_columns = json.load(f)["features_modele_principal"]

    gold = pd.read_parquet(gold_path)
    features = numeric_feature_columns(gold, feature_columns)

    reference = gold[gold["split"] == "train"]
    current = gold[gold["split"] == "test"]

    table = drift_table(reference, current, features)
    for _, row in table.iterrows():
        drift_psi.labels(feature=row["feature"]).set(row["psi"])
        drift_ks_pvalue.labels(feature=row["feature"]).set(row["ks_pvalue"])
        drift_alerte.labels(feature=row["feature"]).set(1 if row["psi"] > PSI_ALERT_THRESHOLD else 0)

    return len(features)


def main() -> None:
    start_http_server(PORT)
    print(f"Exporteur dérive démarré sur :{PORT}/metrics (recalcul toutes les {REFRESH_SECONDS}s)")
    while True:
        n = _reload()
        print(f"{n} feature(s) évaluée(s) depuis {GOLD_DIR}")
        time.sleep(REFRESH_SECONDS)


if __name__ == "__main__":
    main()
