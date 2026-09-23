"""Hachage et manifestes de traçabilité, factorisés depuis `sha256_of()` -- dupliquée à
l'identique dans les notebooks 01/02/03 (`hashlib.sha256(Path(path).read_bytes()).hexdigest()`).

Chaque couche (Bronze, Silver, Gold) écrit un manifeste qui référence le sha256 de sa/ses
source(s) et le sha256 de son propre fichier produit -- ça forme la chaîne de hash vérifiable
décrite dans `data/README.md`. `write_manifest`/`read_manifest` ne font que centraliser le
JSON UTF-8 indenté déjà utilisé partout, sans changer le format.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_manifest(path: Path, manifest: dict[str, Any]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return path


def read_manifest(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
