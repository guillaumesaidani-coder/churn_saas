"""Mesure d'impact par groupe témoin (D12, révisée le 2026-10-03).

Avec une échéance mensuelle (H06), un témoin « traité un mois plus tard » n'est jamais traité
avant son échéance. D12 retient donc trois mesures complémentaires :
- **B, en Haute** : `PART_TEMOIN_HAUTE` des comptes Haute, tirés au hasard, reçoivent l'email au
  lieu de l'appel ; les appels libérés vont aux comptes Moyenne suivants dans l'ordre de perte
  attendue (groupe `renfort`), la capacité D10 reste entière. Mesure : gain de l'appel sur l'email.
- **D, en Moyenne** : `PART_TEMOIN_MOYENNE` des comptes Moyenne signalés, tirés au hasard, ne
  reçoivent pas l'email. Mesure : effet de l'email.
- **C, en contrôle** : comptes à moins de `BANDE_SEUIL` du seuil D9, de part et d'autre, sans
  tirage. Mesure : effet de l'email à la marge du seuil.

Le cycle se déroule en trois temps :
1. au scoring (`tirer_groupes_d12`, `suivi_du_cycle`) : chaque compte reçoit un groupe ; le fichier
   de suivi ne garde que ce qu'il faut pour la mesure (pas de probabilité, pas de variables) ;
2. au cycle suivant, une fois l'échéance passée (`rapprocher_issues`) : le suivi est rapproché de
   l'issue réelle ; seuls des agrégats sont écrits au journal des scores ;
3. chaque trimestre (D13, `consolider`) : les agrégats des cycles sont additionnés.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.production import lire_journal
from src.scoring import recommander_action

PART_TEMOIN_HAUTE = 0.20     # option B
PART_TEMOIN_MOYENNE = 0.10   # option D
BANDE_SEUIL = 0.05           # option C : écart maximal au seuil D9, en probabilité

ACTION_TEMOIN_MOYENNE = "Pas d'email ce cycle (groupe témoin D12) ; surveillance passive"

GROUPES = ("traite", "temoin", "renfort", "hors_protocole")

# Colonnes du fichier de suivi conservé jusqu'au rapprochement : le strict nécessaire à la mesure.
COLONNES_SUIVI = ["cycle", "client_id", "priorite", "signale_D9", "filet_D14", "groupe_D12", "bande_seuil_D12"]

# Sous-groupes comparés au rapprochement : nom -> condition sur le fichier de suivi.
_SOUS_GROUPES = {
    "haute_traite": lambda s: (s["priorite"] == "Haute") & (s["groupe_D12"] == "traite"),
    "haute_temoin": lambda s: (s["priorite"] == "Haute") & (s["groupe_D12"] == "temoin"),
    "renfort": lambda s: s["groupe_D12"] == "renfort",
    "moyenne_traite": lambda s: (s["priorite"] == "Moyenne") & s["signale_D9"] & (s["groupe_D12"] == "traite"),
    "moyenne_temoin": lambda s: (s["priorite"] == "Moyenne") & (s["groupe_D12"] == "temoin"),
    "seuil_dessus": lambda s: s["bande_seuil_D12"] & s["signale_D9"] & (s["priorite"] == "Moyenne")
                              & (s["groupe_D12"] == "traite"),
    "seuil_dessous": lambda s: s["bande_seuil_D12"] & ~s["signale_D9"] & ~s["filet_D14"],
}

# Écart mesuré = churn du premier sous-groupe - churn du second.
_ECARTS = {
    "B_gain_appel_sur_email": ("haute_temoin", "haute_traite"),
    "D_effet_email": ("moyenne_temoin", "moyenne_traite"),
    "C_effet_email_au_seuil": ("seuil_dessous", "seuil_dessus"),
}


def graine_du_cycle(cycle: str) -> int:
    """Graine du tirage, dérivée de l'identifiant du cycle : rejouer un cycle redonne le même
    tirage, sans qu'on puisse choisir la graine après coup."""
    return int(hashlib.sha256(cycle.encode("utf-8")).hexdigest()[:8], 16)


def tirer_groupes_d12(resultats: pd.DataFrame, graine: int,
                      part_haute: float = PART_TEMOIN_HAUTE,
                      part_moyenne: float = PART_TEMOIN_MOYENNE) -> pd.DataFrame:
    """Ajoute `groupe_D12` à la sortie de `assigner_priorites` et ajuste `action_recommandee`.
    La priorité, elle, reste celle de la règle : c'est sur elle que portent les comparaisons."""
    rng = np.random.default_rng(graine)
    out = resultats.copy()
    out["groupe_D12"] = "hors_protocole"

    haute = out.index[out["priorite"] == "Haute"]
    out.loc[haute, "groupe_D12"] = "traite"
    n_temoins_haute = round(len(haute) * part_haute)
    temoins_haute = rng.choice(haute, size=n_temoins_haute, replace=False) if n_temoins_haute else []
    out.loc[temoins_haute, "groupe_D12"] = "temoin"
    out.loc[temoins_haute, "action_recommandee"] = recommander_action("Moyenne")

    # Les appels libérés vont aux comptes Moyenne signalés suivants (rang de perte attendue).
    moyenne = out[(out["priorite"] == "Moyenne") & out["signale_D9"]].sort_values("rang_perte_attendue")
    renfort = moyenne.index[:len(temoins_haute)]
    out.loc[renfort, "groupe_D12"] = "renfort"
    out.loc[renfort, "action_recommandee"] = recommander_action("Haute")

    reste = moyenne.index[len(temoins_haute):]
    out.loc[reste, "groupe_D12"] = "traite"
    n_temoins_moyenne = round(len(reste) * part_moyenne)
    temoins_moyenne = rng.choice(reste, size=n_temoins_moyenne, replace=False) if n_temoins_moyenne else []
    out.loc[temoins_moyenne, "groupe_D12"] = "temoin"
    out.loc[temoins_moyenne, "action_recommandee"] = ACTION_TEMOIN_MOYENNE
    return out


def suivi_du_cycle(resultats: pd.DataFrame, cycle: str, seuil_d9: float) -> pd.DataFrame:
    """Fichier de suivi d'un cycle (sortie de `tirer_groupes_d12`) : identifiant, priorité,
    groupe, et appartenance à la bande autour du seuil (option C). Ni probabilité, ni variables."""
    suivi = resultats.assign(
        cycle=cycle,
        bande_seuil_D12=(resultats["score_churn"] - seuil_d9).abs() < BANDE_SEUIL,
    )
    return suivi[COLONNES_SUIVI].reset_index(drop=True)


def resume_groupes(resultats: pd.DataFrame) -> dict[str, int]:
    """Effectifs par priorité et groupe, pour le journal des scores."""
    effectifs = resultats.groupby(["priorite", "groupe_D12"]).size()
    return {f"{p.lower()}_{g}": int(n) for (p, g), n in effectifs.items()}


def _taux(n: int, churn: int) -> float | None:
    return round(churn / n, 4) if n else None


def _ecart(a: dict, b: dict) -> dict[str, Any]:
    """Écart de churn a - b, avec un intervalle de confiance à 95 % (approximation normale)."""
    if not a["comptes"] or not b["comptes"]:
        return {"ecart": None, "ic95": None}
    pa, pb = a["churn"] / a["comptes"], b["churn"] / b["comptes"]
    erreur = math.sqrt(pa * (1 - pa) / a["comptes"] + pb * (1 - pb) / b["comptes"])
    return {"ecart": round(pa - pb, 4), "ic95": [round(pa - pb - 1.96 * erreur, 4), round(pa - pb + 1.96 * erreur, 4)]}


def _agreger(comptes: dict[str, dict], issues_connues: int, churn_total: int, churn_signales: int) -> dict[str, Any]:
    for valeurs in comptes.values():
        valeurs["taux_churn"] = _taux(valeurs["comptes"], valeurs["churn"])
    return {
        "comptes_rapproches": issues_connues,
        "churn_observe": churn_total,
        "churn_signales_D9": churn_signales,
        "rappel_reel": _taux(churn_total, churn_signales),
        "groupes": comptes,
        "ecarts": {nom: _ecart(comptes[a], comptes[b]) for nom, (a, b) in _ECARTS.items()},
    }


def rapprocher_issues(suivi: pd.DataFrame, issues: pd.DataFrame) -> dict[str, Any]:
    """Suivi d'un cycle + issues réelles (`client_id`, `churn` en 0/1) -> agrégats, sans aucune
    donnée par compte. Un compte sans issue connue est compté à part et exclu des taux."""
    lien = suivi.merge(issues[["client_id", "churn"]], on="client_id", how="left")
    connus = lien[lien["churn"].notna()].copy()
    connus["churn"] = connus["churn"].astype(int)
    comptes = {}
    for nom, condition in _SOUS_GROUPES.items():
        groupe = connus[condition(connus)]
        comptes[nom] = {"comptes": int(len(groupe)), "churn": int(groupe["churn"].sum())}
    agregats = _agreger(comptes, int(len(connus)), int(connus["churn"].sum()),
                        int(connus.loc[connus["signale_D9"], "churn"].sum()))
    agregats["comptes_sans_issue"] = int(lien["churn"].isna().sum())
    return agregats


def consolider(agregats_par_cycle: list[dict[str, Any]]) -> dict[str, Any]:
    """Bilan D13 : additionne les effectifs de plusieurs rapprochements et recalcule taux et écarts."""
    comptes = {nom: {"comptes": 0, "churn": 0} for nom in _SOUS_GROUPES}
    issues_connues = churn_total = churn_signales = 0
    for agregats in agregats_par_cycle:
        for nom in comptes:
            comptes[nom]["comptes"] += agregats["groupes"][nom]["comptes"]
            comptes[nom]["churn"] += agregats["groupes"][nom]["churn"]
        issues_connues += agregats["comptes_rapproches"]
        churn_total += agregats["churn_observe"]
        churn_signales += agregats["churn_signales_D9"]
    consolide = _agreger(comptes, issues_connues, churn_total, churn_signales)
    consolide["cycles"] = len(agregats_par_cycle)
    return consolide


def completer_journal(chemin_journal: Path, cycle: str, agregats: dict[str, Any]) -> dict[str, Any]:
    """Ajoute les agrégats du rapprochement (`issues`) à l'entrée du cycle, sans changer l'ordre
    du journal (la purge des fichiers de suivi s'appuie sur cet ordre)."""
    entrees = lire_journal(chemin_journal)
    cibles = [e for e in entrees if e["cycle"] == cycle]
    if not cibles:
        raise KeyError(f"cycle absent du journal des scores : {cycle!r}")
    cibles[0]["issues"] = agregats
    Path(chemin_journal).write_text(
        "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entrees), encoding="utf-8")
    return cibles[0]
