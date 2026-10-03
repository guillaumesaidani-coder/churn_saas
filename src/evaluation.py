"""Évaluation d'un modèle de churn, critères de promotion et déclencheurs de ré-entraînement.

Reprend, hors notebook, les calculs du §9 du notebook de certification (métriques de test,
baseline métier D8, calibration) pour qu'ils puissent tourner :
- dans la CI, sur le modèle en service (`scripts/evaluer_modele.py`) : le modèle livré doit
  toujours tenir ses critères ;
- au ré-entraînement, pour comparer un challenger au modèle en service sur le même jeu de test
  (`scripts/challenger.py`).

Les critères de promotion sont ceux du runbook (§3) : D8, rappel au seuil D9, PR-AUC au moins
égale au modèle en service, calibration, aucun contrôle bloquant de la base de connaissance.
Les déclencheurs sont ceux du notebook §13.2.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (average_precision_score, brier_score_loss, precision_score, recall_score,
                             roc_auc_score)

GAIN_MIN_D8 = 0.15             # D8 : PR-AUC >= baseline métier + 0,15
RAPPEL_CIBLE_D9 = 0.80         # D9 : rappel >= 80 % au seuil
ECART_CALIBRATION_MAX = 0.05   # probabilité moyenne prédite à moins de 5 points du taux observé
GAIN_PR_AUC_PROMOTION = 0.005  # un challenger ne remplace le modèle en service que s'il fait mieux
TOLERANCE_REPRODUCTION = 0.002 # écart admis entre les métriques recalculées et `metrics.json`

# Déclencheurs de ré-entraînement (notebook §13.2, runbook §3)
PSI_SEUIL_ALERTE = 0.25        # dérive d'une variable du top 5 d'importance
RAPPEL_REEL_MIN = 0.75         # rappel réel d'un cycle dont les issues sont connues
FACTEUR_VOLUME_SIGNALES = 2.0  # part de signalés > 2 fois la valeur habituelle
TOP_IMPORTANCE = 5


def score_regle_metier(X: pd.DataFrame, mediane_integrations: float) -> pd.Series:
    """Baseline D8 (notebook §8) : ancienneté faible, peu d'intégrations, connexion ancienne = risque."""
    return (-X["anciennete_mois"] / 36
            - X["nb_integrations"].fillna(mediane_integrations) / 16
            + X["derniere_connexion_jours"] / 200)


def metriques_classification(y: pd.Series, proba: np.ndarray, score_regle: pd.Series, seuil_d9: float,
                             taux_reference: float) -> dict[str, Any]:
    """Métriques de test du notebook (§9.3) et calibration (§9.4). `taux_reference` est le taux de
    churn du jeu d'entraînement : le score de Brier d'une prédiction constante à ce taux sert de
    référence de calibration."""
    signales = proba >= seuil_d9
    m = {
        "roc_auc": roc_auc_score(y, proba),
        "pr_auc": average_precision_score(y, proba),
        "pr_auc_baseline_metier_D8": average_precision_score(y, score_regle),
        "rappel_seuil_D9": recall_score(y, signales),
        "precision_seuil_D9": precision_score(y, signales, zero_division=0),
        "part_signales_seuil_D9": float(signales.mean()),
        "brier": brier_score_loss(y, proba),
        "brier_reference": brier_score_loss(y, np.full(len(y), taux_reference)),
        "probabilite_moyenne": float(np.mean(proba)),
        "taux_churn_observe": float(np.mean(y)),
    }
    m["gain_pr_auc_vs_D8"] = m["pr_auc"] - m["pr_auc_baseline_metier_D8"]
    return {k: (round(float(v), 4) if isinstance(v, (float, np.floating)) else v) for k, v in m.items()}


def _critere(nom: str, valeur, seuil: str, respecte: bool) -> dict[str, Any]:
    return {"critere": nom, "valeur": valeur, "seuil": seuil, "respecte": bool(respecte)}


def criteres_modele(m: dict[str, Any], controles: pd.DataFrame) -> list[dict[str, Any]]:
    """Critères qu'un modèle doit tenir seul, qu'il soit en service ou candidat."""
    ecart_calibration = abs(m["probabilite_moyenne"] - m["taux_churn_observe"])
    bloquants = int((controles["gravite"] == "bloquant").sum()) if len(controles) else 0
    return [
        _critere("D8 : PR-AUC >= baseline métier + 0,15", m["gain_pr_auc_vs_D8"], f">= {GAIN_MIN_D8}",
                 m["gain_pr_auc_vs_D8"] >= GAIN_MIN_D8),
        _critere("D9 : rappel au seuil sur le test", m["rappel_seuil_D9"], f">= {RAPPEL_CIBLE_D9}",
                 m["rappel_seuil_D9"] >= RAPPEL_CIBLE_D9),
        _critere("Calibration : Brier sous la référence", m["brier"], f"< {m['brier_reference']}",
                 m["brier"] < m["brier_reference"]),
        _critere("Calibration : probabilité moyenne proche du taux observé", round(ecart_calibration, 4),
                 f"<= {ECART_CALIBRATION_MAX}", ecart_calibration <= ECART_CALIBRATION_MAX),
        _critere("Base de connaissance : aucun contrôle bloquant", bloquants, "= 0", bloquants == 0),
    ]


def criteres_reproduction(m: dict[str, Any], metriques_publiees: dict[str, Any]) -> list[dict[str, Any]]:
    """Le modèle livré redonne-t-il les métriques publiées dans `metrics.json` ? Un écart signale
    un artefact qui ne correspond plus au notebook (mauvais fichier, données modifiées)."""
    return [_critere(f"Reproduction de {cle} publiée", m[cle], f"{metriques_publiees[cle]} ± {TOLERANCE_REPRODUCTION}",
                     abs(m[cle] - metriques_publiees[cle]) <= TOLERANCE_REPRODUCTION)
            for cle in ("pr_auc", "roc_auc", "rappel_seuil_D9", "pr_auc_baseline_metier_D8")]


def decider_promotion(criteres_challenger: list[dict], m_challenger: dict, m_champion: dict) -> dict[str, Any]:
    """Décision sur un challenger évalué sur le même jeu de test que le modèle en service.
    Promouvable si tous ses critères tiennent et s'il bat le modèle en service d'au moins
    `GAIN_PR_AUC_PROMOTION` de PR-AUC ; sinon le modèle en service est conservé. La mise en
    service reste une décision humaine (runbook §3)."""
    ecart = round(m_challenger["pr_auc"] - m_champion["pr_auc"], 4)
    comparaison = _critere("PR-AUC au moins égale au modèle en service", ecart, ">= 0", ecart >= 0)
    criteres = criteres_challenger + [comparaison]
    echecs = [c["critere"] for c in criteres if not c["respecte"]]
    if echecs:
        decision, motif = "refuse", "critère(s) non tenu(s) : " + " ; ".join(echecs)
    elif ecart < GAIN_PR_AUC_PROMOTION:
        decision, motif = "champion_conserve", f"critères tenus, mais gain de PR-AUC ({ecart:+.4f}) sous {GAIN_PR_AUC_PROMOTION}"
    else:
        decision, motif = "promouvable", f"critères tenus et PR-AUC {ecart:+.4f} ; mise en service à décider (runbook §3)"
    return {"decision": decision, "motif": motif, "criteres": criteres}


def top_importance(parts: pd.Series, n: int = TOP_IMPORTANCE) -> list[str]:
    """Les `n` variables qui portent la plus grande part de l'explication (`parts_explication`)."""
    return parts.sort_values(ascending=False).head(n).index.tolist()


def declencheurs_cycle(psi: pd.Series, variables_importantes: list[str], part_signales: float,
                       part_signales_reference: float, rappel_reel: float | None = None) -> list[dict[str, Any]]:
    """Déclencheurs évaluables sur un cycle (le calendrier trimestriel se lit dans le journal).
    `psi` : PSI par variable du cycle ; `rappel_reel` : connu seulement au rapprochement."""
    derivees = [v for v in variables_importantes if psi.get(v, 0.0) > PSI_SEUIL_ALERTE]
    resultats = [
        {"declencheur": "derive_top5", "actif": bool(derivees), "detail": derivees,
         "action": "analyser la variable ; ré-entraîner si la performance baisse"},
        {"declencheur": "volume_signales", "actif": part_signales > FACTEUR_VOLUME_SIGNALES * part_signales_reference,
         "detail": round(part_signales / part_signales_reference, 2) if part_signales_reference else None,
         "action": "vérifier l'export en amont avant toute action"},
    ]
    if rappel_reel is not None:
        resultats.append({"declencheur": "rappel_reel", "actif": rappel_reel < RAPPEL_REEL_MIN,
                          "detail": rappel_reel, "action": "ré-entraînement prioritaire"})
    return resultats
