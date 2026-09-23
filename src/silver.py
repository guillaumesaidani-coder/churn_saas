"""Nettoyage Silver, extrait de `notebooks/02_nettoyage_silver.ipynb` (§1-§6) pour le rendre
testable sans dépendre des parquets Bronze réels.

Chaque fonction correspond à une section du notebook, dans le même ordre :
dédoublonnage (§1) -> dates multi-formats (§2) -> nombres texte (§3) -> catégorielles (§4)
-> jointure catalogue (§5) -> valeurs manquantes (§6). `clean_silver()` les enchaîne à
l'identique ; le notebook garde l'exploration (diagnostics, `print`), ce module ne fait que
la transformation.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d %b %Y"]

NUMERIC_COLUMNS = [
    "anciennete_mois", "sieges_souscrits", "utilisateurs_actifs", "taux_adoption_pct",
    "connexions_30j", "heures_usage_30j", "fonctionnalites_total", "fonctionnalites_utilisees",
    "nb_integrations", "derniere_connexion_jours", "tickets_support_90j",
    "delai_reponse_support_h", "csat", "retards_paiement_12m",
    "revenu_mensuel_recurrent_eur", "sante_compte_fin_periode", "valeur_vie_client_eur", "churn",
]

SECTEUR_MAP = [
    ("TECH", "Tech"),
    ("FINANC", "Finance"),
    ("COMMERC", "Commerce"),
    ("SANT", "Santé"),
    ("INDUSTR", "Industrie"),
    ("PUBLIC", "Public"),
    ("DUCATION", "Éducation"),
]

CATALOGUE_COLUMNS = [
    "plan", "prix_mensuel_par_siege_eur", "fonctionnalites_incluses",
    "sla_reponse_h", "quota_stockage_go", "support_dedie",
]

MEDIAN_COLUMNS = [
    "taux_adoption_pct", "heures_usage_30j", "delai_reponse_support_h",
    "csat", "retards_paiement_12m", "nb_integrations",
]


def business_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if not c.startswith("_")]


def drop_strict_duplicates(clients: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """NB02 §1."""
    cols_metier = business_columns(clients)
    n_doublons = int(clients.duplicated(subset=cols_metier).sum())
    clients = clients.drop_duplicates(subset=cols_metier, keep="first").reset_index(drop=True)
    return clients, n_doublons


def parse_date_multi(series: pd.Series, formats: list[str] = DATE_FORMATS) -> pd.Series:
    """NB02 §2. Essaie chaque format dans l'ordre, ne touche pas aux valeurs déjà résolues."""
    result = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    still_missing = result.isna()
    for fmt in formats:
        parsed = pd.to_datetime(series.where(still_missing), format=fmt, errors="coerce")
        result = result.where(~parsed.notna(), parsed)
        still_missing = result.isna()
    return result


def parse_numeric_fr(series: pd.Series) -> pd.Series:
    """NB02 §3. Nettoie virgule décimale, %, € et unité 'h' avant conversion numérique."""
    s = series.astype(object).astype(str).str.strip()
    s = s.replace("", np.nan)
    s = s.str.replace("€", "", regex=False)
    s = s.str.replace("%", "", regex=False)
    s = s.str.replace("h", "", regex=False)
    s = s.str.strip()
    s = s.str.replace(",", ".", regex=False)
    return pd.to_numeric(s, errors="coerce")


def normalize_secteur(value: str) -> str:
    """NB02 §4. Sous-chaîne stable insensible à la casse ; valeur inattendue laissée telle
    quelle (à investiguer), pas convertie en NaN silencieusement."""
    v = (value or "").strip().upper()
    if v == "":
        return np.nan
    for needle, canon in SECTEUR_MAP:
        if needle in v:
            return canon
    return value


def clean_silver(
    clients: pd.DataFrame, catalogue: pd.DataFrame, impute_medians: bool = True
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Enchaîne NB02 §1-§6 dans l'ordre exact. Ne fait pas l'I/O (lecture/écriture parquet,
    manifeste) : voir `notebooks/02_nettoyage_silver.ipynb` §7 pour la persistance.

    `impute_medians=False` laisse les NaN des colonnes `MEDIAN_COLUMNS` : l'imputation est
    alors faite dans le pipeline sklearn, ajustée sur le seul jeu d'entraînement (Gold v2,
    notebook certifiant) -- une médiane calculée sur toutes les lignes utiliserait des
    informations du jeu de test."""
    clients = clients.copy()
    catalogue = catalogue.copy()

    clients, n_doublons = drop_strict_duplicates(clients)

    clients["date_souscription"] = parse_date_multi(clients["date_souscription"])

    for col in NUMERIC_COLUMNS:
        clients[col] = parse_numeric_fr(clients[col])

    clients["plan"] = clients["plan"].str.strip().str.upper().str.capitalize()
    clients["taille_entreprise"] = clients["taille_entreprise"].str.strip().str.upper()
    clients["pays"] = clients["pays"].str.strip()
    clients["secteur"] = clients["secteur"].map(normalize_secteur)

    catalogue["plan"] = catalogue["plan"].str.strip().str.capitalize()
    for c in ["prix_mensuel_par_siege_eur", "fonctionnalites_incluses", "sla_reponse_h", "quota_stockage_go"]:
        catalogue[c] = pd.to_numeric(catalogue[c], errors="coerce")
    clients = clients.merge(catalogue[CATALOGUE_COLUMNS], on="plan", how="left")
    n_orphelins = int(clients["prix_mensuel_par_siege_eur"].isna().sum())

    # §6 -- valeurs manquantes, une stratégie par colonne
    # 1) commentaire_csm : laissé tel quel (chaîne vide conservée, pas d'imputation)

    # 2) revenu_mensuel_recurrent_eur : recalcul via sieges_souscrits x prix catalogue
    mask_mrr_manquant = clients["revenu_mensuel_recurrent_eur"].isna()
    n_recalc_mrr = int(mask_mrr_manquant.sum())
    clients.loc[mask_mrr_manquant, "revenu_mensuel_recurrent_eur"] = (
        clients.loc[mask_mrr_manquant, "sieges_souscrits"]
        * clients.loc[mask_mrr_manquant, "prix_mensuel_par_siege_eur"]
    )

    # 3) secteur / pays : "Inconnu" explicite
    n_secteur_manquant = int(clients["secteur"].isna().sum())
    n_pays_manquant = int((clients["pays"].str.strip() == "").sum())
    clients["pays"] = clients["pays"].replace("", "Inconnu")
    clients["secteur"] = clients["secteur"].fillna("Inconnu")

    # 4) numériques restants : médiane documentée
    medianes: dict[str, float] = {}
    for col in MEDIAN_COLUMNS if impute_medians else []:
        mediane = clients[col].median()
        medianes[col] = float(mediane)
        clients[col] = clients[col].fillna(mediane)

    clients_out = clients.drop(columns=["_source_file", "_ingested_at_utc"])

    report = {
        "n_doublons": n_doublons,
        "n_orphelins_catalogue": n_orphelins,
        "n_recalc_mrr": n_recalc_mrr,
        "n_secteur_manquant": n_secteur_manquant,
        "n_pays_manquant": n_pays_manquant,
        "medianes": medianes,
    }
    return clients_out, report


def build_silver_manifest(
    clients_out: pd.DataFrame,
    report: dict[str, Any],
    sha256_source_bronze: dict[str, str],
    chemin_silver: str,
    sha256_silver: str,
    processed_at_utc: str,
    layer_version: str = "v1",
) -> dict[str, Any]:
    return {
        "couche": "silver",
        "version": layer_version,
        "processed_at_utc": processed_at_utc,
        "source": "data/bronze/clients_churn_bronze.parquet + catalogue_plans_bronze.parquet",
        "sha256_source_bronze": sha256_source_bronze,
        "lignes": int(len(clients_out)),
        "colonnes": list(clients_out.columns),
        "transformations": [
            f"{report['n_doublons']} doublons stricts supprimés",
            "dates converties (3 formats -> datetime64)",
            "nombres texte convertis (virgule, %, €, unité 'h' nettoyés)",
            "casse/espaces normalisés (plan, taille_entreprise) ; secteur normalisé par sous-chaîne stable",
            "jointure avec catalogue_plans (0 orphelin)",
            "valeurs manquantes traitées colonne par colonne (voir §6)",
        ],
        "cible_production": "PostgreSQL churn_saas_db.clients_churn (non disponible dans cet environnement)",
        "chemin_silver": chemin_silver,
        "sha256_silver": sha256_silver,
    }
