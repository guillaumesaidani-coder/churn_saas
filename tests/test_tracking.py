"""Tests unitaires de `src/tracking.py` -- portage du tracking MLflow lié au hash Gold de
py-init/ml (`indusense.modeling.tracking.log_training_run`).

Chaque test pointe vers un store MLflow SQLite jetable dans `tmp_path`, jamais le store réel
du projet -- pour ne pas polluer un futur `data/model/mlflow.db`.
"""
import json

import mlflow
import yaml

from src.tracking import (
    flatten_metrics,
    get_mlflow_tracking_uri,
    log_training_run,
    resolve_tracking_uri,
    write_metrics_and_params,
)


class TestGetMlflowTrackingUri:
    def test_pointe_vers_mlflow_db_dans_le_repertoire_modele(self, tmp_path):
        uri = get_mlflow_tracking_uri(tmp_path)

        assert uri.startswith("sqlite:///")
        assert uri.endswith("mlflow.db")
        assert str(tmp_path.name) in uri


class TestLogTrainingRun:
    def test_run_est_cree_avec_params_metriques_et_tag_gold(self, tmp_path):
        uri = get_mlflow_tracking_uri(tmp_path)

        run_id = log_training_run(
            run_name="rf_v1",
            params={"n_estimators": 200, "max_depth": 10},
            metrics={"pr_auc_test": 0.759, "roc_auc_test": 0.88},
            tracking_uri=uri,
            gold_sha256="c3f400321b24",
            gold_dataset_path="data/gold/clients_churn_gold.parquet",
        )

        mlflow.set_tracking_uri(uri)
        run = mlflow.get_run(run_id)

        assert run.data.params["n_estimators"] == "200"
        assert run.data.metrics["pr_auc_test"] == 0.759
        assert run.data.tags["gold_sha256"] == "c3f400321b24"
        assert run.data.tags["gold_dataset"] == "data/gold/clients_churn_gold.parquet"

    def test_sans_gold_sha256_aucun_tag_gold_nest_pose(self, tmp_path):
        uri = get_mlflow_tracking_uri(tmp_path)

        run_id = log_training_run(
            run_name="essai_sans_gold",
            params={"n_estimators": 100},
            metrics={"pr_auc_test": 0.5},
            tracking_uri=uri,
        )

        mlflow.set_tracking_uri(uri)
        run = mlflow.get_run(run_id)

        assert "gold_sha256" not in run.data.tags


class TestWriteMetricsAndParams:
    def test_ecrit_metrics_json_et_params_yaml(self, tmp_path):
        metrics_path, params_path = write_metrics_and_params(
            metrics={"pr_auc_test": 0.759},
            params={"n_estimators": 200},
            out_dir=tmp_path,
            gold_sha256="c3f400321b24",
        )

        assert json.loads(metrics_path.read_text(encoding="utf-8")) == {"pr_auc_test": 0.759}
        params_out = yaml.safe_load(params_path.read_text(encoding="utf-8"))
        assert params_out == {"n_estimators": 200, "gold_sha256": "c3f400321b24"}

    def test_gold_sha256_absent_si_non_fourni(self, tmp_path):
        _, params_path = write_metrics_and_params(
            metrics={"pr_auc_test": 0.5}, params={"n_estimators": 50}, out_dir=tmp_path,
        )

        params_out = yaml.safe_load(params_path.read_text(encoding="utf-8"))
        assert "gold_sha256" not in params_out


class TestResolveTrackingUri:
    def test_prefere_la_variable_d_environnement(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MLFLOW_TRACKING_URI", "https://dagshub.com/user/repo.mlflow")

        assert resolve_tracking_uri(tmp_path) == "https://dagshub.com/user/repo.mlflow"

    def test_repli_sur_sqlite_local_sans_variable(self, tmp_path, monkeypatch):
        monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)

        assert resolve_tracking_uri(tmp_path) == get_mlflow_tracking_uri(tmp_path)


class TestFlattenMetrics:
    def test_aplatit_les_dicts_imbriques_et_ignore_le_non_numerique(self):
        flat = flatten_metrics({
            "baseline": {"roc_auc": 0.5},
            "modele_retenu": "Régression logistique",
            "verif": True,
            "matrice": [[1, 2], [3, 4]],
            "rang": 12,
        })

        assert flat == {"baseline.roc_auc": 0.5, "rang": 12.0}


class TestLogTrainingRunArtefacts:
    def test_tags_et_artefacts_sont_enregistres(self, tmp_path):
        uri = get_mlflow_tracking_uri(tmp_path)
        artefact = tmp_path / "model_card.md"
        artefact.write_text("# carte", encoding="utf-8")

        run_id = log_training_run(
            run_name="avec_artefacts",
            params={"a": 1},
            metrics={"m": 0.1},
            tracking_uri=uri,
            tags={"modele_retenu": "RL"},
            artifacts=[artefact],
            artifact_location=(tmp_path / "mlartifacts").as_uri(),
        )

        mlflow.set_tracking_uri(uri)
        run = mlflow.get_run(run_id)
        noms = [f.path for f in mlflow.artifacts.list_artifacts(run_id=run_id)]

        assert run.data.tags["modele_retenu"] == "RL"
        assert "model_card.md" in noms
