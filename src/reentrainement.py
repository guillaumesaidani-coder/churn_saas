"""Ré-entraînement : un challenger entraîné hors notebook, comparé au modèle en service.

Le pipeline reprend exactement celui du notebook de certification (§8 et §9 : one-hot des
catégorielles, imputation médiane et standardisation des numériques), le seuil D9 est recalculé
hors pli sur le jeu d'entraînement (jamais le test), et les deux modèles sont évalués sur le même
jeu de test du Gold v2. Chaque comparaison laisse une ligne dans le journal des décisions
(`ajouter_decision`), qu'elle conduise ou non à une promotion.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.evaluation import RAPPEL_CIBLE_D9, criteres_modele, metriques_classification, score_regle_metier
from src.explain import controler_modele, reference_explication
from src.features import CATEGORIELLES_V2, FEATURES_V2, NUMERIQUES_V2
from src.scoring import calibrer_seuil_d9

RANDOM_STATE = 42
FAMILLES = ("logistique", "foret", "boosting")


def pipeline_modele(estimateur, standardiser: bool = True) -> Pipeline:
    """Même préparation que le notebook (§8.2)."""
    etapes_num = [("imputation", SimpleImputer(strategy="median"))]
    if standardiser:
        etapes_num.append(("standardisation", StandardScaler()))
    preparation = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORIELLES_V2),
        ("num", Pipeline(etapes_num), NUMERIQUES_V2),
    ])
    return Pipeline([("preparation", preparation), ("modele", estimateur)])


def construire_challenger(famille: str, C: float = 0.03) -> Pipeline:
    """Les trois familles comparées au notebook (§8.3), non entraînées."""
    if famille == "logistique":
        return pipeline_modele(LogisticRegression(C=C, max_iter=3000))
    if famille == "foret":
        return pipeline_modele(RandomForestClassifier(n_estimators=400, min_samples_leaf=2,
                                                      random_state=RANDOM_STATE, n_jobs=-1), standardiser=False)
    if famille == "boosting":
        return pipeline_modele(HistGradientBoostingClassifier(learning_rate=0.05, max_iter=300,
                                                              random_state=RANDOM_STATE), standardiser=False)
    raise ValueError(f"famille inconnue : {famille!r} (attendu : {FAMILLES})")


def decouper(gold: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
    train = gold[gold["split"] == "train"].reset_index(drop=True)
    test = gold[gold["split"] == "test"].reset_index(drop=True)
    return train[FEATURES_V2], train["churn"], test[FEATURES_V2], test["churn"]


def entrainer(pipeline: Pipeline, X_train: pd.DataFrame, y_train: pd.Series) -> tuple[Pipeline, float]:
    """Entraîne le pipeline et calcule son seuil D9 sur des prédictions hors pli du train."""
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    hors_pli = cross_val_predict(clone(pipeline), X_train, y_train, cv=cv, method="predict_proba")[:, 1]
    seuil = calibrer_seuil_d9(y_train, hors_pli, rappel_cible=RAPPEL_CIBLE_D9)
    return clone(pipeline).fit(X_train, y_train), round(float(seuil), 4)


def controles(pipeline: Pipeline, base: dict, X_train: pd.DataFrame,
              reference: dict | None = None) -> tuple[pd.DataFrame, str]:
    """Contrôles de la base de connaissance : complets pour un modèle linéaire, limités aux
    exclusions et à la couverture des variables sinon (pas de décomposition exacte)."""
    if hasattr(pipeline.named_steps["modele"], "coef_"):
        reference = reference or reference_explication(pipeline, X_train)
        return controler_modele(FEATURES_V2, base, pipeline, reference, X_train), "complets"
    return controler_modele(FEATURES_V2, base), "exclusions et couverture seulement"


def evaluer(pipeline: Pipeline, seuil_d9: float, X_train: pd.DataFrame, y_train: pd.Series,
            X_test: pd.DataFrame, y_test: pd.Series, base: dict,
            reference: dict | None = None) -> dict[str, Any]:
    """Métriques de test, contrôles et critères d'un modèle déjà entraîné."""
    proba = pipeline.predict_proba(X_test)[:, 1]
    regle = score_regle_metier(X_test, X_train["nb_integrations"].median())
    m = metriques_classification(y_test, proba, regle, seuil_d9, taux_reference=float(y_train.mean()))
    table, portee = controles(pipeline, base, X_train, reference)
    return {"seuil_D9": seuil_d9, "metriques": m, "controles": portee,
            "controles_bloquants": int((table["gravite"] == "bloquant").sum()),
            "criteres": criteres_modele(m, table)}


def ajouter_decision(chemin: Path, entree: dict[str, Any]) -> None:
    """Journal des décisions de ré-entraînement : une ligne JSON par comparaison, jamais réécrite."""
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    entree = {"horodatage_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), **entree}
    with chemin.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entree, ensure_ascii=False) + "\n")
