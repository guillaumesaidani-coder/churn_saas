"""Cycle mensuel de production : lots d'export simulés, scoring d'un cycle, journal des scores.

En l'absence d'un vrai export CRM du mois suivant, `simuler_export_mensuel` fabrique un export
« M+1 » au **format de l'export brut** à partir de la table Silver : les mêmes comptes, un mois
plus tard. Deux variantes :
- `stable` : ancienneté + 1 mois, léger bruit sur l'usage (connexions, heures, tickets) ;
- `derive` : la même évolution, plus la baisse d'engagement simulée au §13.1 du notebook
  (connexion plus ancienne de 30 jours, une intégration de moins, CSAT en baisse d'un point,
  40 % d'usage en moins).
Les colonnes connues seulement après coup (`sante_compte_fin_periode`, `valeur_vie_client_eur`,
`churn`) sont laissées vides : au moment du scoring, on ne les connaît pas.

Le lot simulé repasse ensuite par **la même chaîne** qu'à l'entraînement (`preparer_lot` :
`load_raw` → `clean_silver` → `construire_features_v2`), puis par le système de décision
(`scorer_cycle`). Chaque cycle laisse une trace dans un journal (`ajouter_au_journal`) : quel
modèle a scoré quels comptes, avec quel seuil, sur quel export. Le fichier de suivi par compte
(`src.mesure_impact.suivi_du_cycle`) est conservé 2 cycles (`purger_scores`), le temps d'observer
l'issue réelle : c'est la base de la mesure des comptes sauvés (D12/D13).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.bronze import load_raw
from src.features import construire_features_v2
from src.scoring import assigner_priorites, scorer_batch
from src.silver import clean_silver
from src.versioning import sha256_of

# Colonnes de l'export CRM brut, dans l'ordre du fichier fourni par l'énoncé.
COLONNES_EXPORT = [
    "client_id", "date_souscription", "jour_souscription", "secteur", "pays", "taille_entreprise",
    "plan", "anciennete_mois", "sieges_souscrits", "utilisateurs_actifs", "taux_adoption_pct",
    "connexions_30j", "heures_usage_30j", "fonctionnalites_total", "fonctionnalites_utilisees",
    "nb_integrations", "derniere_connexion_jours", "tickets_support_90j", "delai_reponse_support_h",
    "csat", "retards_paiement_12m", "revenu_mensuel_recurrent_eur", "couleur_theme_interface",
    "code_datacenter", "groupe_experimentation", "commentaire_csm", "sante_compte_fin_periode",
    "valeur_vie_client_eur", "churn",
]

# Connues seulement après la période observée : vides dans un export de scoring.
COLONNES_CONNUES_APRES_COUP = ["sante_compte_fin_periode", "valeur_vie_client_eur", "churn"]

# Bruit d'un mois ordinaire : (colonne, nombre de décimales). Écart-type de 5 % (log-normal).
BRUIT_USAGE = [("connexions_30j", 0), ("heures_usage_30j", 1), ("tickets_support_90j", 0)]
ECART_TYPE_BRUIT = 0.05

# Baisse d'engagement simulée, identique au lot dérivé du §13.1 du notebook.
DERIVE_ENGAGEMENT = {
    "derniere_connexion_jours": "+30 jours",
    "nb_integrations": "-1 (minimum 0)",
    "csat": "-1 point (minimum 1)",
    "heures_usage_30j": "x 0,6",
}

MODES = ("stable", "derive")


def simuler_export_mensuel(silver: pd.DataFrame, mode: str, graine: int = 42) -> pd.DataFrame:
    """Table Silver (sortie de `clean_silver`) -> export brut du mois suivant, en texte, avec les
    colonnes de `COLONNES_EXPORT`. Déterministe pour une graine donnée."""
    if mode not in MODES:
        raise ValueError(f"mode inconnu : {mode!r} (attendu : {MODES})")
    rng = np.random.default_rng(graine)
    lot = silver.copy()

    lot["anciennete_mois"] = lot["anciennete_mois"] + 1
    for colonne, decimales in BRUIT_USAGE:
        facteur = rng.lognormal(mean=0.0, sigma=ECART_TYPE_BRUIT, size=len(lot))
        lot[colonne] = (lot[colonne] * facteur).round(decimales)

    if mode == "derive":
        lot["derniere_connexion_jours"] = lot["derniere_connexion_jours"] + 30
        lot["nb_integrations"] = (lot["nb_integrations"] - 1).clip(lower=0)
        lot["csat"] = (lot["csat"] - 1).clip(lower=1)
        lot["heures_usage_30j"] = (lot["heures_usage_30j"] * 0.6).round(1)

    for colonne in COLONNES_CONNUES_APRES_COUP:
        lot[colonne] = np.nan
    return _vers_format_export(lot)


def _vers_format_export(lot: pd.DataFrame) -> pd.DataFrame:
    """Typé -> texte, comme un export CRM : dates ISO, nombres sans « .0 » superflu, vide pour
    une valeur manquante."""
    export = pd.DataFrame(index=lot.index)
    for colonne in COLONNES_EXPORT:
        valeurs = lot[colonne]
        if colonne == "date_souscription":
            export[colonne] = pd.to_datetime(valeurs).dt.strftime("%Y-%m-%d").fillna("")
        elif pd.api.types.is_numeric_dtype(valeurs):
            export[colonne] = valeurs.map(_nombre_en_texte)
        else:
            export[colonne] = valeurs.fillna("").astype(str)
    return export.reset_index(drop=True)


def _nombre_en_texte(valeur: float) -> str:
    if pd.isna(valeur):
        return ""
    if float(valeur).is_integer():
        return str(int(valeur))
    return f"{valeur:.6f}".rstrip("0").rstrip(".")


def preparer_lot(chemin_export: Path, catalogue: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Export brut -> (20 features du Gold v2, identifiants), par la même chaîne qu'à
    l'entraînement. Les valeurs manquantes restent au pipeline du modèle."""
    brut = load_raw(Path(chemin_export), ingested_at=datetime.now(timezone.utc).isoformat())
    silver, _ = clean_silver(brut, catalogue, impute_medians=False)
    return construire_features_v2(silver), silver["client_id"]


def scorer_cycle(X: pd.DataFrame, client_ids: pd.Series, modele_churn, modele_clv,
                 seuil_d9: float, capacite_d10: int) -> pd.DataFrame:
    """Score de churn, CLV estimée, perte attendue, priorité et action recommandée par compte."""
    return assigner_priorites(scorer_batch(X, client_ids, modele_churn, modele_clv), seuil_d9, capacite_d10)


def version_fichier(chemin: Path) -> str:
    """Version d'un artefact = début de son empreinte SHA-256 (12 caractères)."""
    return sha256_of(Path(chemin))[:12]


def entree_journal(cycle: str, resultats: pd.DataFrame, *, export: Path, modele_churn: Path,
                   modele_clv: Path, gold_sha256: str, seuil_d9: float, capacite_d10: int,
                   psi_max: float | None = None, variables_en_alerte: list[str] | None = None,
                   horodatage: str | None = None) -> dict[str, Any]:
    """Une ligne du journal des scores : de quoi retrouver, pour un cycle, le modèle, l'export et
    la règle utilisés, et résumer ce que le cycle a produit (sans aucune donnée par compte)."""
    priorites = resultats["priorite"].value_counts()
    return {
        "cycle": cycle,
        "horodatage_utc": horodatage or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "export": Path(export).as_posix(),
        "sha256_export": sha256_of(Path(export)),
        "version_modele_churn": version_fichier(modele_churn),
        "version_modele_clv": version_fichier(modele_clv),
        "gold_sha256_entrainement": gold_sha256,
        "seuil_D9": round(float(seuil_d9), 4),
        "capacite_D10": int(capacite_d10),
        "comptes_scores": int(len(resultats)),
        "comptes_signales": int(resultats["signale_D9"].sum()),
        "part_signales": round(float(resultats["signale_D9"].mean()), 4),
        "priorite_haute": int(priorites.get("Haute", 0)),
        "priorite_moyenne": int(priorites.get("Moyenne", 0)),
        "score_moyen": round(float(resultats["score_churn"].mean()), 4),
        "perte_attendue_totale_eur": round(float(resultats["perte_attendue_eur"].sum()), 0),
        "psi_max": None if psi_max is None else round(float(psi_max), 4),
        "variables_en_alerte": variables_en_alerte or [],
    }


def lire_journal(chemin_journal: Path) -> list[dict[str, Any]]:
    chemin_journal = Path(chemin_journal)
    if not chemin_journal.exists():
        return []
    lignes = chemin_journal.read_text(encoding="utf-8").splitlines()
    return [json.loads(ligne) for ligne in lignes if ligne.strip()]


def ajouter_au_journal(chemin_journal: Path, entree: dict[str, Any]) -> list[dict[str, Any]]:
    """Ajoute l'entrée au journal (une ligne JSON par cycle). Rejouer un cycle remplace son
    entrée au lieu de la dupliquer : le journal reste une ligne par cycle, dans l'ordre."""
    entrees = [e for e in lire_journal(chemin_journal) if e["cycle"] != entree["cycle"]]
    entrees.append(entree)
    chemin_journal = Path(chemin_journal)
    chemin_journal.parent.mkdir(parents=True, exist_ok=True)
    chemin_journal.write_text(
        "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entrees), encoding="utf-8")
    return entrees


def purger_scores(dossier_scores: Path, cycles_du_journal: list[str], conserver: int,
                  prefixe: str = "suivi_") -> list[str]:
    """Supprime les fichiers par compte (`<prefixe><cycle>.parquet`) des cycles plus anciens que
    les `conserver` derniers du journal (limitation de la conservation). Le journal, lui, ne
    contient que des agrégats et reste complet. Renvoie les cycles purgés."""
    a_garder = set(cycles_du_journal[-conserver:]) if conserver > 0 else set()
    purges = []
    for fichier in sorted(Path(dossier_scores).glob(f"{prefixe}*.parquet")):
        cycle = fichier.stem.removeprefix(prefixe)
        if cycle not in a_garder:
            fichier.unlink()
            purges.append(cycle)
    return purges
