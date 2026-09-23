"""Recherche d'hyperparamètres pour le modèle churn, portée du mécanisme Optuna du projet
InduSense (`py-init/ml/TP11.ipynb` + `src/indusense/modeling/{pipeline,train}.py`) : espace de
recherche explicite, objectif = PR-AUC moyenne en validation croisée, sampler TPE seedé pour
reproductibilité -- adapté ici à `StratifiedKFold` (pas de groupe machine à préserver, à la
différence d'InduSense) et à la forêt aléatoire, seul des deux modèles de
`04_modelisation_churn.ipynb` §3 avec un espace d'hyperparamètres qui vaut la peine d'être
exploré (la régression logistique §2 n'a qu'un seul hyperparamètre significatif, `C`, déjà
laissé à sa valeur par défaut).

`search_best_params()` ne fait pas l'entraînement final ni le calcul des métriques test : ça
reste dans le notebook (§8, comme le fit final de `train_and_evaluate()` côté InduSense), pour
que le run tracé par `src/tracking.py` porte bien sur le modèle réellement retenu.
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import optuna
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

RANDOM_STATE = 42
N_TRIALS = 30
N_FOLDS = 5

PipelineBuilder = Callable[[dict], Pipeline]


def build_rf_pipeline(cat_cols: list[str], num_cols: list[str], params: dict, random_state: int = RANDOM_STATE) -> Pipeline:
    """Même structure que le pipeline forêt aléatoire de NB04 §3 (OneHot + passthrough),
    hyperparamètres du classifieur injectés plutôt que figés en dur."""
    preprocessor = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols),
        ("num", "passthrough", num_cols),
    ])
    return Pipeline([
        ("prep", preprocessor),
        ("clf", RandomForestClassifier(random_state=random_state, n_jobs=-1, **params)),
    ])


def cv_pr_auc(
    pipeline_builder: PipelineBuilder,
    X: pd.DataFrame,
    y: pd.Series,
    params: dict,
    n_splits: int = N_FOLDS,
    random_state: int = RANDOM_STATE,
) -> float:
    """PR-AUC moyenne sur `n_splits` folds stratifiés -- même métrique que le critère de
    sélection déjà retenu en NB04 §4 (PR-AUC, pas ROC-AUC, en classe déséquilibrée).
    Retourne 0.0 si un fold ne contient aucun positif (garde-fou identique à
    `indusense.modeling` côté objectif Optuna)."""
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    scores = []
    for tr_idx, vl_idx in skf.split(X, y):
        X_tr, y_tr = X.iloc[tr_idx], y.iloc[tr_idx]
        X_vl, y_vl = X.iloc[vl_idx], y.iloc[vl_idx]

        if y_vl.sum() < 2:
            continue

        pipe = pipeline_builder(params)
        pipe.fit(X_tr, y_tr)
        y_prob = pipe.predict_proba(X_vl)[:, 1]
        scores.append(average_precision_score(y_vl, y_prob))

    return float(np.mean(scores)) if scores else 0.0


def make_objective(
    pipeline_builder: PipelineBuilder,
    X: pd.DataFrame,
    y: pd.Series,
    n_splits: int = N_FOLDS,
    random_state: int = RANDOM_STATE,
):
    def objective(trial: optuna.Trial) -> float:
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 600),
            "max_depth": trial.suggest_int("max_depth", 3, 30),
            "min_samples_leaf": trial.suggest_int("min_samples_leaf", 1, 20),
            "max_features": trial.suggest_categorical("max_features", ["sqrt", "log2", None]),
        }
        return cv_pr_auc(pipeline_builder, X, y, params, n_splits=n_splits, random_state=random_state)

    return objective


def search_best_params(
    pipeline_builder: PipelineBuilder,
    X: pd.DataFrame,
    y: pd.Series,
    n_trials: int = N_TRIALS,
    n_splits: int = N_FOLDS,
    random_state: int = RANDOM_STATE,
    show_progress_bar: bool = False,
) -> tuple[dict, optuna.Study]:
    """Lance l'étude Optuna (TPESampler seedé -> même séquence de trials à chaque rejeu) et
    renvoie les meilleurs hyperparamètres ainsi que l'étude complète (pour inspection,
    `study.trials_dataframe()`, etc.)."""
    objective = make_objective(pipeline_builder, X, y, n_splits=n_splits, random_state=random_state)
    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=random_state),
    )
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study.optimize(objective, n_trials=n_trials, show_progress_bar=show_progress_bar)
    return dict(study.best_params), study
