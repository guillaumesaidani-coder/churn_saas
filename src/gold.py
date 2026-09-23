"""Feature engineering et split Gold, extraits de `notebooks/03_preparation_gold.ipynb`
(§1-§6) pour les rendre testables sans dépendre du parquet Silver réel.

`EXCLUDED_COLUMNS_CHURN`/`EXCLUDED_COLUMNS_CLV` et `build_gold()` reproduisent la décision
anti-fuite du notebook : `sante_compte_fin_periode` est conservée dans la table Gold pour la
traçabilité (et alimente la régression CLV) mais exclue du X des deux modèles, par principe
de disponibilité au moment du scoring -- pas seulement parce que sa corrélation avec le churn
est extrême (§1, cf. aussi `gold_manifest.json` -> `piege_de_fuite`).
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split

NUMERIC_CANDIDATES = [
    "anciennete_mois", "sieges_souscrits", "utilisateurs_actifs", "taux_adoption_pct",
    "connexions_30j", "heures_usage_30j", "fonctionnalites_total", "fonctionnalites_utilisees",
    "nb_integrations", "derniere_connexion_jours", "tickets_support_90j",
    "delai_reponse_support_h", "csat", "retards_paiement_12m", "revenu_mensuel_recurrent_eur",
]

CATEGORICAL_CANDIDATES = [
    "secteur", "pays", "taille_entreprise", "plan", "jour_souscription",
    "couleur_theme_interface", "code_datacenter", "groupe_experimentation",
]

SEUIL_CORR = 0.03
SEUIL_CRAMER = 0.05

EXCLUDED_COLUMNS_CHURN = [
    "client_id", "date_souscription", "commentaire_csm",
    "sante_compte_fin_periode", "valeur_vie_client_eur", "churn",
]

EXCLUDED_COLUMNS_CLV = ["client_id", "split", "sante_compte_fin_periode", "churn", "valeur_vie_client_eur"]


def leakage_correlation_and_auc(clients: pd.DataFrame, colonne: str = "sante_compte_fin_periode") -> tuple[float, float]:
    """NB03 §1. Corrélation brute + AUC d'un modèle à cette seule variable -- le signal
    d'alerte qui justifie l'exclusion, pas juste une affirmation."""
    corr = float(clients[colonne].astype(float).corr(clients["churn"].astype(float)))
    X_demo = clients[[colonne]]
    y_demo = clients["churn"]
    modele_demo = LogisticRegression().fit(X_demo, y_demo)
    proba_demo = modele_demo.predict_proba(X_demo)[:, 1]
    auc = float(roc_auc_score(y_demo, proba_demo))
    return corr, auc


def cramers_v(confusion: np.ndarray) -> float:
    chi2 = stats.chi2_contingency(confusion)[0]
    n = confusion.sum()
    k = min(confusion.shape) - 1
    return float(np.sqrt(chi2 / (n * k))) if k > 0 else float("nan")


def identify_leurres(
    clients: pd.DataFrame,
    numeric_candidates: list[str] = NUMERIC_CANDIDATES,
    categorical_candidates: list[str] = CATEGORICAL_CANDIDATES,
    seuil_corr: float = SEUIL_CORR,
    seuil_cramer: float = SEUIL_CRAMER,
) -> list[str]:
    """NB03 §2. Variables à effet quasi nul sur le churn (corrélation point-bisériale pour
    les numériques, V de Cramér pour les catégorielles) -- restent dans les features (§3),
    seulement signalées pour ne pas sur-interpréter leur importance en aval."""
    leurres_num = [
        col for col in numeric_candidates
        if abs(stats.pointbiserialr(clients["churn"], clients[col].astype(float))[0]) < seuil_corr
    ]
    leurres_cat = []
    for col in categorical_candidates:
        table = pd.crosstab(clients[col], clients["churn"])
        if cramers_v(table.values) < seuil_cramer:
            leurres_cat.append(col)
    return leurres_num + leurres_cat


def add_ratio_features(clients: pd.DataFrame) -> pd.DataFrame:
    """NB03 §4."""
    clients = clients.copy()
    clients["taux_utilisation_fonctionnalites"] = (
        clients["fonctionnalites_utilisees"] / clients["fonctionnalites_total"].replace(0, np.nan)
    ).fillna(0)
    clients["taux_retard_paiement_par_mois"] = (
        clients["retards_paiement_12m"] / clients["anciennete_mois"].clip(lower=1)
    )
    return clients


def select_feature_columns(columns: list[str], excluded: list[str] = EXCLUDED_COLUMNS_CHURN) -> list[str]:
    return [c for c in columns if c not in excluded]


def assign_split(clients: pd.DataFrame, test_size: float = 0.2, random_state: int = 42) -> pd.Series:
    """NB03 §5. Split stratifié sur `churn`, reproductible via `random_state`."""
    train_idx, test_idx = train_test_split(
        clients.index, test_size=test_size, stratify=clients["churn"], random_state=random_state,
    )
    split = pd.Series("train", index=clients.index, name="split")
    split.loc[test_idx] = "test"
    return split


def build_gold(clients: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Enchaîne NB03 §1-§6 dans l'ordre exact. Ne fait pas l'I/O (lecture Silver, écriture
    Gold, manifeste) : voir `notebooks/03_preparation_gold.ipynb` pour la persistance."""
    clients = clients.copy()
    corr_fuite, auc_demo = leakage_correlation_and_auc(clients)
    leurres = identify_leurres(clients)

    clients = add_ratio_features(clients)
    feature_columns = select_feature_columns(list(clients.columns))
    clients["split"] = assign_split(clients)

    colonnes_gold = ["client_id", "split"] + feature_columns + [
        "sante_compte_fin_periode", "valeur_vie_client_eur", "churn",
    ]
    gold = clients[colonnes_gold].copy()

    feature_columns_clv = select_feature_columns(list(gold.columns), EXCLUDED_COLUMNS_CLV)
    corr_sante_clv = float(
        clients["sante_compte_fin_periode"].astype(float).corr(clients["valeur_vie_client_eur"].astype(float))
    )
    corr_sante_log_clv = float(
        clients["sante_compte_fin_periode"].astype(float)
        .corr(np.log1p(clients["valeur_vie_client_eur"].astype(float)))
    )

    recap_split = gold.groupby("split")["churn"].mean() * 100

    info = {
        "corr_fuite": round(corr_fuite, 3),
        "auc_demo": round(auc_demo, 3),
        "leurres": leurres,
        "feature_columns": feature_columns,
        "feature_columns_clv": feature_columns_clv,
        "taux_churn_train_pct": float(round(recap_split.get("train", float("nan")), 1)),
        "taux_churn_test_pct": float(round(recap_split.get("test", float("nan")), 1)),
        "corr_sante_clv": round(corr_sante_clv, 3),
        "corr_sante_log_clv": round(corr_sante_log_clv, 3),
    }
    return gold, info


def build_gold_manifest(
    gold: pd.DataFrame,
    info: dict[str, Any],
    sha256_source_silver: str,
    chemin_gold: str,
    sha256_gold: str,
    processed_at_utc: str,
    random_state: int = 42,
    test_size: float = 0.2,
    layer_version: str = "v1",
) -> dict[str, Any]:
    return {
        "couche": "gold",
        "version": layer_version,
        "processed_at_utc": processed_at_utc,
        "source": "data/silver/clients_churn_silver.parquet",
        "sha256_source_silver": sha256_source_silver,
        "lignes": int(len(gold)),
        "colonnes": list(gold.columns),
        "features_modele_principal": info["feature_columns"],
        "leurres_identifies": info["leurres"],
        "colonnes_exclues_du_modele": EXCLUDED_COLUMNS_CHURN,
        "piege_de_fuite": {
            "colonne": "sante_compte_fin_periode",
            "correlation_avec_churn": info["corr_fuite"],
            "auc_modele_1_variable": info["auc_demo"],
            "conservee_dans_gold_pour": (
                "traçabilité et régression CLV -- exclue du X des deux modèles (churn §3, CLV §8) "
                "pour la même raison temporelle, pas seulement pour le churn"
            ),
        },
        "cible_secondaire": "valeur_vie_client_eur (régression, jamais utilisée comme feature du modèle principal)",
        "split": {
            "méthode": "train_test_split stratifié sur churn",
            "random_state": random_state,
            "test_size": test_size,
            "taux_churn_train_pct": info["taux_churn_train_pct"],
            "taux_churn_test_pct": info["taux_churn_test_pct"],
        },
        "chemin_gold": chemin_gold,
        "sha256_gold": sha256_gold,
        "cible_secondaire_features": {
            "colonnes_exclues_clv": EXCLUDED_COLUMNS_CLV,
            "feature_columns_clv": info["feature_columns_clv"],
            "identique_a_feature_columns_modele_principal": set(info["feature_columns_clv"]) == set(info["feature_columns"]),
            "correlation_sante_compte_fin_periode_vs_clv": info["corr_sante_clv"],
            "correlation_sante_compte_fin_periode_vs_log_clv": info["corr_sante_log_clv"],
            "principe": (
                "variable calculée en fin de période exclue par principe de disponibilité au "
                "scoring, indépendamment de la force de corrélation mesurée"
            ),
        },
    }
