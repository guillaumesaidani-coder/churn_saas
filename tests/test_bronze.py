"""Tests unitaires de `src/bronze.py` (logique de `notebooks/01_ingestion_bronze.ipynb` §1, §6).

Données utilisées : jamais les CSV réels de `Examen_cas d'usage candidat/` -- uniquement des
CSV synthétiques minimaux écrits dans `tmp_path`, pour isoler la mécanique d'ingestion
(traçabilité, pas de correction) du contenu métier réel.
"""
import pandas as pd

from src.bronze import bronze_table_entry, build_bronze_manifest, load_raw, write_bronze
from src.versioning import sha256_of


def _write_csv(tmp_path, name: str, content: str):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


class TestLoadRaw:
    def test_ajoute_les_colonnes_de_provenance(self, tmp_path):
        csv_path = _write_csv(tmp_path, "clients.csv", "client_id,plan\nCLI-1,Pro\n")

        df = load_raw(csv_path, ingested_at="2026-01-01T00:00:00+00:00")

        assert list(df.columns[:2]) == ["_source_file", "_ingested_at_utc"]
        assert df["_source_file"].tolist() == ["clients.csv"]
        assert df["_ingested_at_utc"].tolist() == ["2026-01-01T00:00:00+00:00"]

    def test_tout_est_lu_en_texte_brut_rien_nest_corrige(self, tmp_path):
        # "007" perdrait ses zéros de tête si lu comme entier -- le Bronze ne corrige rien.
        csv_path = _write_csv(tmp_path, "clients.csv", "client_id,code\nCLI-1,007\n")

        df = load_raw(csv_path, ingested_at="2026-01-01T00:00:00+00:00")

        assert df["code"].tolist() == ["007"]

    def test_cellules_vides_restent_des_chaines_vides_pas_des_nan(self, tmp_path):
        csv_path = _write_csv(tmp_path, "clients.csv", "client_id,commentaire\nCLI-1,\n")

        df = load_raw(csv_path, ingested_at="2026-01-01T00:00:00+00:00")

        assert df["commentaire"].tolist() == [""]


class TestWriteBronze:
    def test_ecrit_un_parquet_relisible_a_lidentique(self, tmp_path):
        df = pd.DataFrame({"client_id": ["CLI-1", "CLI-2"], "plan": ["Pro", "Basic"]})

        out_path = write_bronze(df, tmp_path / "bronze", "clients_churn_bronze")

        assert out_path == tmp_path / "bronze" / "clients_churn_bronze.parquet"
        pd.testing.assert_frame_equal(pd.read_parquet(out_path), df)


class TestBronzeTableEntry:
    def test_hash_source_et_hash_bronze_correspondent_aux_fichiers_reels(self, tmp_path):
        csv_path = _write_csv(tmp_path, "clients.csv", "client_id\nCLI-1\n")
        df = pd.DataFrame({"client_id": ["CLI-1"]})
        bronze_path = write_bronze(df, tmp_path / "bronze", "clients_churn_bronze")

        entry = bronze_table_entry(df, "clients.csv", raw_dir=tmp_path, bronze_path=bronze_path)

        assert entry["lignes"] == 1
        assert entry["colonnes"] == ["client_id"]
        assert entry["sha256_source_csv"] == sha256_of(csv_path)
        assert entry["sha256_bronze"] == sha256_of(bronze_path)


class TestBuildBronzeManifest:
    def test_assemble_les_tables_sous_la_bonne_structure(self):
        tables = {"clients_churn_bronze": {"lignes": 5035}}

        manifest = build_bronze_manifest(tables, ingested_at="2026-01-01T00:00:00+00:00")

        assert manifest["couche"] == "bronze"
        assert manifest["version"] == "v1"
        assert manifest["tables"] == tables
        assert "Aucune transformation" in manifest["avertissement"]
