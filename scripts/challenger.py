#!/usr/bin/env python
"""Entraîne un challenger, le compare au modèle en service et trace la décision.

Le challenger est entraîné sur le split `train` du Gold v2 indiqué (après un nouvel export, le
Gold v2 régénéré par `dvc repro`), avec la même préparation que le notebook ; son seuil D9 est
recalculé hors pli. Les deux modèles sont évalués sur le même jeu de test, puis
`decider_promotion` rend l'une de trois décisions :
- `promouvable` : critères tenus et gain de PR-AUC suffisant ; la mise en service reste une
  décision humaine (runbook §3 : choix du modèle au notebook, rejeu, CI, publication) ;
- `champion_conserve` : critères tenus, mais pas de gain suffisant ;
- `refuse` : au moins un critère non tenu.

Chaque comparaison est ajoutée au journal des décisions
(`data/reentrainement/journal_decisions.jsonl`), quelle que soit la décision. Aucun artefact du
modèle en service n'est modifié.

Usage : python scripts/challenger.py --famille logistique --declencheur calendrier
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.evaluation import decider_promotion  # noqa: E402
from src.explain import charger_base_connaissance  # noqa: E402
from src.production import version_fichier  # noqa: E402
from src.reentrainement import (  # noqa: E402
    FAMILLES, ajouter_decision, construire_challenger, decouper, entrainer, evaluer,
)
from src.versioning import read_manifest, sha256_of  # noqa: E402

DECLENCHEURS = ("calendrier", "derive_top5", "rappel_reel", "volume_signales", "demonstration")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--famille", choices=FAMILLES, default="logistique")
    parser.add_argument("--C", type=float, default=0.03, help="régularisation (famille logistique)")
    parser.add_argument("--declencheur", choices=DECLENCHEURS, required=True)
    parser.add_argument("--model-dir", type=Path, default=Path("data/model_v2"))
    parser.add_argument("--gold", type=Path, default=Path("data/gold/clients_churn_gold_v2.parquet"))
    parser.add_argument("--base", type=Path, default=Path("knowledge/base_connaissance.yaml"))
    parser.add_argument("--journal", type=Path, default=Path("data/reentrainement/journal_decisions.jsonl"))
    args = parser.parse_args()

    base = charger_base_connaissance(args.base)
    X_train, y_train, X_test, y_test = decouper(pd.read_parquet(args.gold))

    champion = joblib.load(args.model_dir / "model.joblib")
    seuil_champion = read_manifest(args.model_dir / "scoring_manifest.json")["regle_decision"]["seuil_D9_valeur"]
    eval_champion = evaluer(champion, seuil_champion, X_train, y_train, X_test, y_test, base,
                            read_manifest(args.model_dir / "explication_reference.json"))

    challenger, seuil_challenger = entrainer(construire_challenger(args.famille, args.C), X_train, y_train)
    eval_challenger = evaluer(challenger, seuil_challenger, X_train, y_train, X_test, y_test, base)
    decision = decider_promotion(eval_challenger["criteres"], eval_challenger["metriques"], eval_champion["metriques"])

    config = {"famille": args.famille, **({"C": args.C} if args.famille == "logistique" else {})}
    ajouter_decision(args.journal, {
        "declencheur": args.declencheur,
        "gold_sha256": sha256_of(args.gold),
        "champion": {"version": version_fichier(args.model_dir / "model.joblib"), "seuil_D9": seuil_champion,
                     "metriques": eval_champion["metriques"]},
        "challenger": {"configuration": config, "seuil_D9": seuil_challenger, "controles": eval_challenger["controles"],
                       "metriques": eval_challenger["metriques"]},
        **decision,
        "mise_en_service": "non : décision humaine, procédure du runbook §3",
    })

    for c in decision["criteres"]:
        print(f"{'OK ' if c['respecte'] else 'KO '} {c['critere']} : {c['valeur']} (attendu {c['seuil']})")
    print(f"PR-AUC test : challenger {eval_challenger['metriques']['pr_auc']} / "
          f"en service {eval_champion['metriques']['pr_auc']}")
    print(f"Décision : {decision['decision']} ({decision['motif']}) -> {args.journal.as_posix()}")


if __name__ == "__main__":
    main()
