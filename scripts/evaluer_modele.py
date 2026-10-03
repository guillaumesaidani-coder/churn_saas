#!/usr/bin/env python
"""Évalue le modèle en service sur le jeu de test du Gold v2 : porte de qualité de la CI.

Recalcule les métriques de test du modèle livré (`data/model_v2/model.joblib`, seuil D9 de
`scoring_manifest.json`) et vérifie :
- les critères qu'il doit tenir (D8, rappel au seuil D9, calibration, aucun contrôle bloquant de
  la base de connaissance) ;
- qu'il redonne les métriques publiées dans `metrics.json` (artefact cohérent avec le notebook).

Sort avec le code 1 si un critère n'est pas tenu : la CI échoue et l'image n'est pas construite.
Avec `--sortie`, écrit le rapport complet en JSON.

Usage : python scripts/evaluer_modele.py [--sortie reports/evaluation_modele.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.evaluation import criteres_reproduction  # noqa: E402
from src.explain import charger_base_connaissance  # noqa: E402
from src.reentrainement import decouper, evaluer  # noqa: E402
from src.versioning import read_manifest  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model-dir", type=Path, default=Path("data/model_v2"))
    parser.add_argument("--gold", type=Path, default=Path("data/gold/clients_churn_gold_v2.parquet"))
    parser.add_argument("--base", type=Path, default=Path("knowledge/base_connaissance.yaml"))
    parser.add_argument("--sortie", type=Path, help="rapport JSON (facultatif)")
    args = parser.parse_args()

    modele = joblib.load(args.model_dir / "model.joblib")
    seuil = read_manifest(args.model_dir / "scoring_manifest.json")["regle_decision"]["seuil_D9_valeur"]
    reference = read_manifest(args.model_dir / "explication_reference.json")
    publiees = read_manifest(args.model_dir / "metrics.json")
    X_train, y_train, X_test, y_test = decouper(pd.read_parquet(args.gold))

    rapport = evaluer(modele, seuil, X_train, y_train, X_test, y_test,
                      charger_base_connaissance(args.base), reference)
    rapport["criteres"] += criteres_reproduction(rapport["metriques"], publiees)
    rapport["modele"] = (args.model_dir / "model.joblib").as_posix()
    rapport["tous_respectes"] = all(c["respecte"] for c in rapport["criteres"])

    for c in rapport["criteres"]:
        print(f"{'OK ' if c['respecte'] else 'KO '} {c['critere']} : {c['valeur']} (attendu {c['seuil']})")
    if args.sortie:
        args.sortie.parent.mkdir(parents=True, exist_ok=True)
        args.sortie.write_text(json.dumps(rapport, ensure_ascii=False, indent=2), encoding="utf-8")
    if not rapport["tous_respectes"]:
        sys.exit("Le modèle en service ne tient pas tous ses critères.")
    print("Le modèle en service tient tous ses critères.")


if __name__ == "__main__":
    main()
