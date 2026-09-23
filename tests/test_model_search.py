"""Tests unitaires de `src/model_search.py` -- portage du mécanisme de recherche
d'hyperparamètres Optuna de py-init/ml (TP11.ipynb) vers le modèle churn.

Données utilisées : uniquement un jeu synthétique séparable, généré avec un `Generator`
numpy seedé -- jamais le Gold réel -- pour garder les tests rapides et déterministes.
"""
import numpy as np
import optuna
import pandas as pd

from src.model_search import build_rf_pipeline, cv_pr_auc, search_best_params

optuna.logging.set_verbosity(optuna.logging.WARNING)


def _separable_dataset(n: int = 200, seed: int = 0) -> tuple[pd.DataFrame, pd.Series]:
    rng = np.random.default_rng(seed)
    y = rng.integers(0, 2, size=n)
    signal = np.where(y == 1, rng.normal(2, 0.5, n), rng.normal(-2, 0.5, n))
    X = pd.DataFrame({
        "signal_num": signal,
        "bruit_num": rng.normal(0, 1, n),
        "categorie": rng.choice(["A", "B", "C"], size=n),
    })
    return X, pd.Series(y)


def _builder(X: pd.DataFrame):
    def build(params: dict):
        return build_rf_pipeline(cat_cols=["categorie"], num_cols=["signal_num", "bruit_num"], params=params)
    return build


class TestBuildRfPipeline:
    def test_contient_un_preprocesseur_et_un_classifieur(self):
        pipe = build_rf_pipeline(cat_cols=["categorie"], num_cols=["signal_num"], params={"n_estimators": 50})

        assert [name for name, _ in pipe.steps] == ["prep", "clf"]
        assert pipe.named_steps["clf"].n_estimators == 50


class TestCvPrAuc:
    def test_dataset_separable_donne_un_score_eleve(self):
        X, y = _separable_dataset()

        score = cv_pr_auc(_builder(X), X, y, params={"n_estimators": 100, "max_depth": 5, "min_samples_leaf": 1, "max_features": "sqrt"})

        assert 0.0 <= score <= 1.0
        assert score > 0.8  # signal très marqué -- un score bas signalerait un bug de câblage

    def test_score_reproductible_a_seed_fixe(self):
        X, y = _separable_dataset()
        params = {"n_estimators": 80, "max_depth": 4, "min_samples_leaf": 2, "max_features": "sqrt"}

        score_a = cv_pr_auc(_builder(X), X, y, params, random_state=42)
        score_b = cv_pr_auc(_builder(X), X, y, params, random_state=42)

        assert score_a == score_b


class TestSearchBestParams:
    def test_retourne_un_dict_de_params_et_une_etude(self):
        X, y = _separable_dataset()

        best_params, study = search_best_params(_builder(X), X, y, n_trials=3)

        assert set(best_params) == {"n_estimators", "max_depth", "min_samples_leaf", "max_features"}
        assert isinstance(study, optuna.Study)
        assert len(study.trials) == 3

    def test_meme_seed_donne_les_memes_meilleurs_params(self):
        X, y = _separable_dataset()

        best_a, _ = search_best_params(_builder(X), X, y, n_trials=3, random_state=42)
        best_b, _ = search_best_params(_builder(X), X, y, n_trials=3, random_state=42)

        assert best_a == best_b
