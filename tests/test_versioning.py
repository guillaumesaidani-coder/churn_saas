"""Tests unitaires de `src/versioning.py` -- le socle du chaînage de hash Bronze -> Silver
-> Gold documenté dans `data/README.md`."""
import hashlib

from src.versioning import read_manifest, sha256_of, write_manifest


def test_sha256_of_correspond_a_hashlib_direct(tmp_path):
    fichier = tmp_path / "exemple.txt"
    fichier.write_bytes(b"contenu versionne")

    assert sha256_of(fichier) == hashlib.sha256(b"contenu versionne").hexdigest()


def test_sha256_of_change_si_le_contenu_change(tmp_path):
    fichier = tmp_path / "exemple.txt"
    fichier.write_bytes(b"v1")
    hash_v1 = sha256_of(fichier)

    fichier.write_bytes(b"v2")
    hash_v2 = sha256_of(fichier)

    assert hash_v1 != hash_v2


def test_write_puis_read_manifest_est_un_aller_retour_fidele(tmp_path):
    manifest = {"couche": "bronze", "version": "v1", "lignes": 5000}
    chemin = tmp_path / "sous_dossier" / "manifest.json"

    write_manifest(chemin, manifest)

    assert chemin.exists()
    assert read_manifest(chemin) == manifest
