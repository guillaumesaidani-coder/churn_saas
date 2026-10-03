#!/usr/bin/env python
"""Rapproche le suivi d'un cycle des issues réelles, une fois l'échéance passée (D12, H06).

À lancer au cycle M+1 pour le cycle M : lit `<sortie>/scores/suivi_<cycle>.parquet`, le joint au
fichier des issues (une ligne par compte : `client_id`, `churn` en 0/1, tiré du CRM après
l'échéance), calcule les agrégats de mesure (rappel réel, churn par groupe, écarts B, C et D avec
leur intervalle de confiance) et les ajoute à l'entrée du cycle dans le journal des scores.
Aucune donnée par compte n'est écrite. Le fichier de suivi sera purgé au cycle suivant.

Avec `--consolider`, affiche en plus le bilan de tous les cycles rapprochés du journal (D13).

Usage : python scripts/rapprocher_issues.py --cycle 2026-11 --issues chemin/vers/issues_2026-11.csv
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.mesure_impact import completer_journal, consolider, rapprocher_issues  # noqa: E402
from src.production import lire_journal  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cycle", required=True, help="cycle à rapprocher, ex. 2026-11")
    parser.add_argument("--issues", required=True, type=Path, help="CSV client_id,churn du cycle")
    parser.add_argument("--sortie", type=Path, default=Path("data/production"))
    parser.add_argument("--consolider", action="store_true", help="afficher le bilan de tous les cycles rapprochés")
    args = parser.parse_args()

    chemin_suivi = args.sortie / "scores" / f"suivi_{args.cycle}.parquet"
    if not chemin_suivi.exists():
        sys.exit(f"Suivi introuvable : {chemin_suivi} (cycle jamais scoré, ou déjà purgé)")
    issues = pd.read_csv(args.issues, dtype={"client_id": str})
    agregats = rapprocher_issues(pd.read_parquet(chemin_suivi), issues)
    chemin_journal = args.sortie / "journal_scores.jsonl"
    completer_journal(chemin_journal, args.cycle, agregats)

    print(f"Cycle {args.cycle} : {agregats['comptes_rapproches']} comptes rapprochés, "
          f"{agregats['comptes_sans_issue']} sans issue ; rappel réel {agregats['rappel_reel']}")
    print(json.dumps(agregats["ecarts"], ensure_ascii=False, indent=2))
    if args.consolider:
        rapproches = [e["issues"] for e in lire_journal(chemin_journal) if "issues" in e]
        print("Bilan consolidé (D13) :")
        print(json.dumps(consolider(rapproches)["ecarts"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
