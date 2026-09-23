"""Ingestion Bronze, extraite de `notebooks/01_ingestion_bronze.ipynb` (§1, §6) pour la
rendre testable indépendamment des CSV réels et du répertoire `Examen_cas d'usage candidat`.

Règle d'or reprise telle quelle : le Bronze ne corrige rien. `load_raw` lit tout en texte
brut (`dtype=str, keep_default_na=False`) et se contente d'ajouter deux colonnes de
provenance (`_source_file`, `_ingested_at_utc`) -- aucun dédoublonnage, parsing de date ou
typage numérique (ça, c'est la couche Silver, voir `src/silver.py`).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.versioning import sha256_of


def load_raw(path: Path, ingested_at: str) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    df.insert(0, "_source_file", path.name)
    df.insert(1, "_ingested_at_utc", ingested_at)
    return df


def write_bronze(df: pd.DataFrame, out_dir: Path, name: str) -> Path:
    out_path = Path(out_dir) / f"{name}.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    return out_path


def bronze_table_entry(df: pd.DataFrame, source_file: str, raw_dir: Path, bronze_path: Path) -> dict[str, Any]:
    """Une entrée du bloc `manifest["tables"][name]` (NB01 §6)."""
    return {
        "fichier_source": source_file,
        "lignes": int(len(df)),
        "colonnes": list(df.columns),
        "chemin_bronze": str(bronze_path),
        "sha256_source_csv": sha256_of(Path(raw_dir) / source_file),
        "sha256_bronze": sha256_of(bronze_path),
    }


def build_bronze_manifest(
    tables: dict[str, dict[str, Any]],
    ingested_at: str,
    layer_version: str = "v1",
    avertissement: str = (
        "Données brutes non corrigées. Aucune transformation (dédoublonnage, parsing "
        "de dates, typage numérique, normalisation catégorielle) n'a été appliquée -- "
        "voir la couche Silver."
    ),
) -> dict[str, Any]:
    """`tables` : {nom_table: entrée produite par `bronze_table_entry`}."""
    return {
        "couche": "bronze",
        "version": layer_version,
        "ingested_at_utc": ingested_at,
        "tables": tables,
        "avertissement": avertissement,
    }
