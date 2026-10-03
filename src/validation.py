"""Validation des entrées de l'API : variables connues, types et bornes physiques.

Deux niveaux, à ne pas confondre :
- **bornes physiques** (ici) : une valeur hors de ces bornes est impossible (nombre négatif de
  connexions, satisfaction à 7 sur 5, 13 retards sur 12 mois). La requête est refusée (422) :
  scorer une valeur impossible donnerait un score faux sans erreur visible ;
- **plages du dictionnaire** (base de connaissance) : une valeur hors de la plage observée est
  possible mais inhabituelle. Elle est scorée, avec un avertissement dans l'explication
  (`src.explain.avertissements_entree`).

Les valeurs manquantes (`null`) sont acceptées : le pipeline les impute comme à l'entraînement.
Une modalité inconnue d'une variable catégorielle est acceptée (avertissement dans l'explication).
"""
from __future__ import annotations

import math
from typing import Any

from src.features import CATEGORIELLES_V2, NUMERIQUES_V2

# (minimum, maximum) ; None = non borné de ce côté.
BORNES_PHYSIQUES: dict[str, tuple[float | None, float | None]] = {
    "anciennete_mois": (0, None),
    "sieges_souscrits": (0, None),
    "utilisateurs_actifs": (0, None),
    "taux_adoption_pct": (0, 100),
    "connexions_30j": (0, None),
    "heures_usage_30j": (0, None),
    "fonctionnalites_total": (0, None),
    "fonctionnalites_utilisees": (0, None),
    "nb_integrations": (0, None),
    "derniere_connexion_jours": (0, None),
    "tickets_support_90j": (0, None),
    "delai_reponse_support_h": (0, None),
    "csat": (1, 5),
    "retards_paiement_12m": (0, 12),
    "revenu_mensuel_recurrent_eur": (0, None),
    "taux_utilisation_fonctionnalites": (0, 1),
    "taux_retard_paiement_par_mois": (0, None),   # les valeurs impossibles sont neutralisées ensuite
}

MAX_ERREURS = 20


def _est_nombre(valeur: Any) -> bool:
    return isinstance(valeur, (int, float)) and not isinstance(valeur, bool)


def erreurs_valeur(variable: str, valeur: Any) -> str | None:
    """Raison du refus d'une valeur, ou None si elle est acceptable."""
    if valeur is None:
        return None
    if variable in CATEGORIELLES_V2:
        return None if isinstance(valeur, str) else "texte attendu"
    if variable in NUMERIQUES_V2:
        if not _est_nombre(valeur) or not math.isfinite(valeur):
            return "nombre attendu"
        minimum, maximum = BORNES_PHYSIQUES[variable]
        if (minimum is not None and valeur < minimum) or (maximum is not None and valeur > maximum):
            bornes = f"[{minimum if minimum is not None else '-inf'} ; {maximum if maximum is not None else '+inf'}]"
            return f"{valeur} hors des bornes physiques {bornes}"
        return None
    return None if isinstance(valeur, str) or _est_nombre(valeur) else "nombre ou texte attendu"


def valider_entrees(clients: list[tuple[str, dict[str, Any]]], colonnes: list[str]) -> list[str]:
    """`clients` : (client_id, variables) ; `colonnes` : variables attendues par le modèle servi.
    Renvoie les erreurs (au plus `MAX_ERREURS`), vide si tout est acceptable."""
    attendues = set(colonnes)
    erreurs = []
    for client_id, variables in clients:
        for variable in sorted(set(variables) - attendues):
            erreurs.append(f"{client_id} : variable inconnue « {variable} »")
        for variable in colonnes:
            raison = erreurs_valeur(variable, variables.get(variable))
            if raison:
                erreurs.append(f"{client_id} : {variable} : {raison}")
        if len(erreurs) >= MAX_ERREURS:
            return erreurs[:MAX_ERREURS] + ["(liste tronquée)"]
    return erreurs
