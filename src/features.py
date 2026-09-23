"""Construction des features du Gold v2 (notebook certifiant), à partir d'une table Silver.

Différences avec le Gold v1 (`src/gold.py`) :
- les 5 leurres (effet nul sur le churn, identifiés en §6 du notebook) sont exclus, comme le
  demande l'énoncé (« à identifier et à exclure ») ;
- les 5 colonnes du catalogue sont exclues : chacune ne prend qu'une valeur par `plan`
  (information déjà portée par `plan`, colinéarité parfaite pour un modèle linéaire) ;
- `taux_adoption_pct` manquant est recalculé ligne à ligne (`100 x actifs / sièges`) plutôt
  qu'imputé par une médiane ;
- les autres valeurs manquantes sont laissées en NaN : l'imputation est faite dans le pipeline
  sklearn, ajustée sur le seul jeu d'entraînement.

La même fonction sert à l'entraînement et au scoring d'un export brut : aucune divergence
possible entre les features vues à l'entraînement et celles reçues en production.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.gold import add_ratio_features

LEURRES = [
    "jour_souscription", "pays", "code_datacenter", "couleur_theme_interface", "groupe_experimentation",
]

REDONDANTES_CATALOGUE = [
    "prix_mensuel_par_siege_eur", "fonctionnalites_incluses", "sla_reponse_h",
    "quota_stockage_go", "support_dedie",
]

CATEGORIELLES_V2 = ["secteur", "taille_entreprise", "plan"]

NUMERIQUES_V2 = [
    "anciennete_mois", "sieges_souscrits", "utilisateurs_actifs", "taux_adoption_pct",
    "connexions_30j", "heures_usage_30j", "fonctionnalites_total", "fonctionnalites_utilisees",
    "nb_integrations", "derniere_connexion_jours", "tickets_support_90j",
    "delai_reponse_support_h", "csat", "retards_paiement_12m", "revenu_mensuel_recurrent_eur",
    "taux_utilisation_fonctionnalites", "taux_retard_paiement_par_mois",
]

FEATURES_V2 = CATEGORIELLES_V2 + NUMERIQUES_V2


def completer_taux_adoption(clients: pd.DataFrame) -> pd.DataFrame:
    """`taux_adoption_pct` = 100 x utilisateurs_actifs / sieges_souscrits par définition
    (dictionnaire de données) : une valeur manquante se recalcule exactement, sans imputation
    statistique. Calcul ligne à ligne, donc sans fuite entre train et test."""
    clients = clients.copy()
    recalcul = 100 * clients["utilisateurs_actifs"] / clients["sieges_souscrits"].replace(0, np.nan)
    clients["taux_adoption_pct"] = clients["taux_adoption_pct"].fillna(recalcul.round(1))
    return clients


def construire_features_v2(clients_silver: pd.DataFrame) -> pd.DataFrame:
    """Table Silver (sortie de `clean_silver`, avec ou sans imputation) -> les 20 features du
    Gold v2, dans l'ordre de `FEATURES_V2`. Les NaN restants sont laissés au pipeline."""
    clients = completer_taux_adoption(clients_silver)
    clients = add_ratio_features(clients)
    return clients[FEATURES_V2].copy()
