#!/usr/bin/env python
"""Fabrique deux exports CRM simulés du mois suivant (M+1), au format de l'export brut :
`m1_stable` (un mois ordinaire) et `m1_derive` (baisse d'engagement du §13.1 du notebook).

Les deux lots partent de la même table Silver et du même bruit (même graine) : le lot dérivé
ne diffère du lot stable que par la baisse d'engagement. Un manifeste trace la source, la
graine, les transformations et l'empreinte de chaque lot.

Usage : python scripts/simuler_lots_mensuels.py [--sortie data/production] [--graine 42]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.bronze import load_raw  # noqa: E402
from src.production import (  # noqa: E402
    BRUIT_USAGE, COLONNES_CONNUES_APRES_COUP, DERIVE_ENGAGEMENT, ECART_TYPE_BRUIT, MODES,
    simuler_export_mensuel,
)
from src.silver import clean_silver  # noqa: E402
from src.versioning import sha256_of, write_manifest  # noqa: E402

DOSSIER_BRUT = Path("Examen_cas d'usage candidat")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sortie", type=Path, default=Path("data/production"))
    parser.add_argument("--graine", type=int, default=42)
    args = parser.parse_args()

    source = DOSSIER_BRUT / "churn_saas_complet.csv"
    chemin_catalogue = DOSSIER_BRUT / "catalogue_plans.csv"
    maintenant = datetime.now(timezone.utc).isoformat()
    brut = load_raw(source, ingested_at=maintenant)
    catalogue = pd.read_csv(chemin_catalogue, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    silver, _ = clean_silver(brut, catalogue, impute_medians=False)

    lots = {}
    for mode in MODES:
        chemin = args.sortie / f"m1_{mode}" / "export_crm.csv"
        chemin.parent.mkdir(parents=True, exist_ok=True)
        # Fin de ligne fixée : même fichier, donc même empreinte, sous Windows et sous Linux.
        simuler_export_mensuel(silver, mode, graine=args.graine).to_csv(
            chemin, index=False, encoding="utf-8", lineterminator="\n")
        lots[f"m1_{mode}"] = {"chemin": chemin.as_posix(), "lignes": len(silver), "sha256": sha256_of(chemin)}
        print(f"{chemin} : {len(silver)} comptes")

    write_manifest(args.sortie / "lots_simules_manifest.json", {
        "objet": "exports CRM simulés du mois suivant (M+1), au format de l'export brut",
        "genere_le_utc": maintenant,
        "source": source.as_posix(),
        "sha256_source": sha256_of(source),
        "sha256_catalogue": sha256_of(chemin_catalogue),
        "graine": args.graine,
        "comptes": "les comptes de la table Silver (doublons retirés), reconduits un mois plus tard ; "
                   "population non renouvelée (simplification)",
        "evolution_commune": {
            "anciennete_mois": "+1",
            "bruit_usage": {colonne: f"x lognormal(0, {ECART_TYPE_BRUIT})" for colonne, _ in BRUIT_USAGE},
        },
        "derive_engagement_m1_derive": DERIVE_ENGAGEMENT,
        "colonnes_vides": COLONNES_CONNUES_APRES_COUP,
        "lots": lots,
    })


if __name__ == "__main__":
    main()
