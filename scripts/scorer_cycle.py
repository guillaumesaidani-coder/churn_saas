#!/usr/bin/env python
"""Score un cycle mensuel à partir d'un export CRM brut, et le trace dans le journal des scores.

Étapes : export brut -> même chaîne qu'à l'entraînement (`preparer_lot`) -> modèles v2 et règle
de décision D9/D10/D14 (`scorer_cycle`) -> dérive des 17 variables numériques contre la
référence (split `train` du Gold v2) -> fichiers du cycle et entrée de journal.

Écrit :
- `<sortie>/scores/scores_<cycle>.parquet` : une ligne par compte (score, CLV estimée, perte
  attendue, priorité, action) ; seuls les `--conserver` derniers cycles sont gardés ;
- `<dossier de l'export>/features.parquet` : les 20 variables du cycle (lues par l'exporteur de
  dérive, `scripts/export_drift_metrics.py`) ;
- `<dossier de l'export>/derive.json` : PSI et p-value KS par variable ;
- `<sortie>/journal_scores.jsonl` : une ligne par cycle, sans donnée par compte.

Usage : python scripts/scorer_cycle.py --cycle m1_stable --export data/production/m1_stable/export_crm.csv
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.drift import drift_table  # noqa: E402
from src.features import NUMERIQUES_V2  # noqa: E402
from src.production import (  # noqa: E402
    ajouter_au_journal, entree_journal, preparer_lot, purger_scores, scorer_cycle,
)
from src.versioning import read_manifest  # noqa: E402

PSI_SEUIL_ALERTE = 0.25   # même seuil que l'alerte Prometheus (drift_alert_rules.yml)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cycle", required=True, help="identifiant du cycle, ex. 2026-11 ou m1_stable")
    parser.add_argument("--export", required=True, type=Path, help="export CRM brut du cycle (CSV)")
    parser.add_argument("--catalogue", type=Path, default=Path("Examen_cas d'usage candidat/catalogue_plans.csv"))
    parser.add_argument("--model-dir", type=Path, default=Path("data/model_v2"))
    parser.add_argument("--gold", type=Path, default=Path("data/gold/clients_churn_gold_v2.parquet"))
    parser.add_argument("--sortie", type=Path, default=Path("data/production"))
    parser.add_argument("--conserver", type=int, default=3,
                        help="nombre de cycles dont les scores par compte sont conservés (défaut : 3)")
    args = parser.parse_args()

    regle = read_manifest(args.model_dir / "scoring_manifest.json")["regle_decision"]
    seuil_d9, capacite_d10 = regle["seuil_D9_valeur"], regle["capacite_csm_D10"]
    gold_sha256 = read_manifest(args.model_dir / "model_manifest.json")["gold_sha256"]
    chemin_churn, chemin_clv = args.model_dir / "model.joblib", args.model_dir / "model_clv.joblib"

    catalogue = pd.read_csv(args.catalogue, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    X, client_ids = preparer_lot(args.export, catalogue)
    resultats = scorer_cycle(X, client_ids, joblib.load(chemin_churn), joblib.load(chemin_clv),
                             seuil_d9, capacite_d10)

    gold = pd.read_parquet(args.gold)
    derive = drift_table(gold[gold["split"] == "train"], X, NUMERIQUES_V2).set_index("feature")
    en_alerte = derive.index[derive["psi"] > PSI_SEUIL_ALERTE].tolist()

    dossier_cycle = args.export.parent
    X.assign(client_id=client_ids.values).to_parquet(dossier_cycle / "features.parquet", index=False)
    (dossier_cycle / "derive.json").write_text(json.dumps(
        {"reference": "split train du Gold v2", "seuil_alerte_psi": PSI_SEUIL_ALERTE,
         "variables": derive.round(4).to_dict(orient="index")},
        ensure_ascii=False, indent=2), encoding="utf-8")

    dossier_scores = args.sortie / "scores"
    dossier_scores.mkdir(parents=True, exist_ok=True)
    resultats.to_parquet(dossier_scores / f"scores_{args.cycle}.parquet", index=False)

    entree = entree_journal(
        args.cycle, resultats, export=args.export, modele_churn=chemin_churn, modele_clv=chemin_clv,
        gold_sha256=gold_sha256, seuil_d9=seuil_d9, capacite_d10=capacite_d10,
        psi_max=derive["psi"].max(), variables_en_alerte=en_alerte)
    journal = ajouter_au_journal(args.sortie / "journal_scores.jsonl", entree)
    purges = purger_scores(dossier_scores, [e["cycle"] for e in journal], args.conserver)

    print(f"Cycle {args.cycle} : {entree['comptes_scores']} comptes, {entree['comptes_signales']} signalés "
          f"({entree['part_signales']:.0%}), {entree['priorite_haute']} en priorité haute ; "
          f"modèle {entree['version_modele_churn']}")
    print(f"Dérive : PSI max {entree['psi_max']:.3f} ; variables en alerte (PSI > {PSI_SEUIL_ALERTE}) : "
          f"{en_alerte or 'aucune'}")
    if purges:
        print(f"Scores par compte purgés (plus de {args.conserver} cycles) : {purges}")


if __name__ == "__main__":
    main()
