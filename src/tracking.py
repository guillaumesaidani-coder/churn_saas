"""Trace un entraînement dans MLflow, avec un lien explicite vers la version du Gold dataset
(`gold_sha256`) -- même mécanisme que `indusense.modeling.tracking.log_training_run`
(py-init/ml), adapté à un store SQLite local sous `data/model/` (pas de serveur MLflow à
faire tourner). C'est ce tag qui permet de retrouver, pour un run donné, exactement quelle
version de `clients_churn_gold.parquet` l'a produit (même principe que la chaîne de hash
Bronze -> Silver -> Gold documentée dans `data/README.md`, prolongée jusqu'au modèle).

Écrit aussi `metrics.json`/`params.yaml` en clair à côté du modèle, versionnés par Git -- pas
seulement dans le store MLflow local, qui n'est pas fait pour être diffé.

Si la variable d'environnement `MLFLOW_TRACKING_URI` est définie (ex. serveur MLflow hébergé
par DagsHub), `resolve_tracking_uri` la préfère au store SQLite local : le même code trace
alors les runs sur un serveur consultable par le jury, sans modifier les notebooks.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import mlflow
import yaml

EXPERIMENT_NAME = "churn_saas_training"


def get_mlflow_tracking_uri(model_dir: Path) -> str:
    return f"sqlite:///{Path(model_dir).resolve() / 'mlflow.db'}"


def resolve_tracking_uri(model_dir: Path) -> str:
    """`MLFLOW_TRACKING_URI` si défini (serveur distant), sinon store SQLite local."""
    return os.environ.get("MLFLOW_TRACKING_URI") or get_mlflow_tracking_uri(model_dir)


def flatten_metrics(metrics: dict[str, Any], prefix: str = "") -> dict[str, float]:
    """Aplatit un dict imbriqué (`metrics.json`) en {"a.b": valeur} numériques uniquement --
    MLflow n'accepte que des métriques scalaires. Les booléens et listes sont ignorés."""
    flat: dict[str, float] = {}
    for key, value in metrics.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(flatten_metrics(value, prefix=f"{name}."))
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            flat[name] = float(value)
    return flat


def log_training_run(
    run_name: str,
    params: dict[str, Any],
    metrics: dict[str, Any],
    tracking_uri: str,
    gold_sha256: str | None = None,
    gold_dataset_path: str | None = None,
    experiment_name: str = EXPERIMENT_NAME,
    tags: dict[str, str] | None = None,
    artifacts: list[Path] | None = None,
    artifact_location: str | None = None,
) -> str:
    """Loggue un run MLflow (params + métriques + tag gold_sha256 si fourni, tags et
    fichiers artefacts optionnels). Retourne le run_id créé.

    `artifact_location` n'est utilisé qu'à la création de l'expérience (store local :
    évite que MLflow écrive ses artefacts dans le répertoire courant du notebook)."""
    mlflow.set_tracking_uri(tracking_uri)
    if artifact_location and mlflow.get_experiment_by_name(experiment_name) is None:
        mlflow.create_experiment(experiment_name, artifact_location=artifact_location)
    mlflow.set_experiment(experiment_name)

    with mlflow.start_run(run_name=run_name) as run:
        mlflow.log_params(params)
        mlflow.log_metrics({k: v for k, v in metrics.items() if isinstance(v, (int, float))})
        if gold_sha256:
            mlflow.set_tag("gold_sha256", gold_sha256)
            mlflow.set_tag("gold_dataset", gold_dataset_path or "")
        if tags:
            mlflow.set_tags(tags)
        for path in artifacts or []:
            mlflow.log_artifact(str(path))
        return run.info.run_id


def write_metrics_and_params(
    metrics: dict[str, Any], params: dict[str, Any], out_dir: Path, gold_sha256: str | None = None
) -> tuple[Path, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    metrics_path = out_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")

    params_out = dict(params)
    if gold_sha256:
        params_out["gold_sha256"] = gold_sha256
    params_path = out_dir / "params.yaml"
    params_path.write_text(yaml.safe_dump(params_out, sort_keys=True), encoding="utf-8")

    return metrics_path, params_path
