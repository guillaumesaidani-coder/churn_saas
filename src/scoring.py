"""Logique de scoring batch, réalignée sur `notebooks/06_implementation_scoring.ipynb` (§1,
§2, §3) tels qu'ils existent réellement aujourd'hui -- pour la rendre testable
indépendamment des artefacts `.joblib` et des données Gold réelles.

Version précédente de ce module (priorité par quantile de `valeur_a_risque_eur`) : le
notebook a depuis évolué vers la règle de décision D9 (seuil calibré sur le rappel)
+ D10 (capacité CSM mensuelle) + D14 (tri par perte attendue), documentée dans
`data/model/scoring_manifest.json` -- sans que ce module ait été mis à jour, et sans que le
notebook importe encore ces fonctions (il les redéfinit en cellule). Ce fichier corrige
l'écart : `scorer_batch`/`assigner_priorites`/`recommander_action` reproduisent maintenant la
logique D9/D10/D14 telle qu'exécutée dans le notebook, pas l'ancienne approche par quantile.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import recall_score

ACTIONS_PAR_PRIORITE = {
    "Haute": "Appel personnalisé du CSM référent sous 5 jours ouvrés",
    "Moyenne": "Email ciblé et proposition d'un point d'usage",
    "Basse": "Surveillance passive, sans action dédiée",
}

MOTS_INTERDITS = [
    "automatiquement exécuté",
    "sans validation",
    "résiliation appliquée",
    "downgrade appliqué",
    "sans intervention humaine",
]


def scorer_batch(X: pd.DataFrame, client_ids: pd.Series, model_churn, model_clv) -> pd.DataFrame:
    """NB06 §1. `model_churn`/`model_clv` doivent exposer `predict_proba`/`predict`.
    `perte_attendue_eur` = score_churn x valeur_vie_estimee_eur (D14, sans facteur tau)."""
    score_churn = model_churn.predict_proba(X)[:, 1]
    valeur_vie_estimee = np.expm1(model_clv.predict(X))
    valeur_vie_estimee = np.clip(valeur_vie_estimee, 0, None)

    perte_attendue = score_churn * valeur_vie_estimee

    return pd.DataFrame({
        "client_id": pd.Series(client_ids).values,
        "score_churn": np.round(score_churn, 3),
        "valeur_vie_estimee_eur": np.round(valeur_vie_estimee, 0),
        "perte_attendue_eur": np.round(perte_attendue, 0),
    })


def calibrer_seuil_d9(y_true, score_churn, rappel_cible: float = 0.80) -> float:
    """Calibration D9 (offline, sur un cycle labellisé -- jamais au moment du scoring réel,
    où `churn` n'est par construction pas connu) : le plus grand seuil pour lequel le rappel
    reste >= `rappel_cible`. Valeur figée en production dans `scoring_manifest.json`
    (`seuil_D9_valeur`), à passer telle quelle à `assigner_priorites` pour le scoring réel."""
    seuils_candidats = np.unique(score_churn)
    seuils_valides = [
        s for s in seuils_candidats if recall_score(y_true, score_churn >= s) >= rappel_cible
    ]
    return float(max(seuils_valides)) if seuils_valides else 0.0


def assigner_priorites(resultats: pd.DataFrame, seuil_d9: float, capacite_haute: int) -> pd.DataFrame:
    """NB06 §2. D9 (signalement par seuil de rappel) + D10 (capacité CSM mensuelle) + D14
    (tri par perte attendue) -> 3 tiers. `resultats` doit contenir `client_id`, `score_churn`,
    `perte_attendue_eur` (sortie de `scorer_batch`)."""
    out = resultats.copy()
    out["signale_D9"] = out["score_churn"] >= seuil_d9

    signales = out[out["signale_D9"]].sort_values("perte_attendue_eur", ascending=False)
    client_ids_haute = set(signales.head(capacite_haute)["client_id"])

    def _priorite(row):
        if not row["signale_D9"]:
            return "Basse"
        return "Haute" if row["client_id"] in client_ids_haute else "Moyenne"

    out["priorite"] = out.apply(_priorite, axis=1)
    out["action_recommandee"] = out["priorite"].map(recommander_action)
    return out


def recommander_action(priorite: str) -> str:
    return ACTIONS_PAR_PRIORITE[priorite]


def action_est_conforme_d3(action: str) -> bool:
    """NB06 §3. D3 / art. 22 RGPD : aucune formulation ne doit décrire une action
    irréversible exécutée sans intervention humaine (résiliation, downgrade automatique)."""
    action_min = action.lower()
    return not any(mot in action_min for mot in MOTS_INTERDITS)
