"""Explicabilité du modèle de churn, confrontée à la base de connaissance du projet
(`knowledge/base_connaissance.yaml`).

Trois usages, tous déterministes :

1. **Expliquer un score.** Pour la régression logistique, le logit du score se décompose
   exactement en une somme de contributions, une par variable :
   contribution = coefficient x (valeur transformée - valeur de référence), la référence
   étant la moyenne du jeu d'entraînement. Propriété vérifiable :
   logit de référence + somme des contributions = logit du modèle. Pour un modèle linéaire,
   ces contributions sont exactement les valeurs SHAP (variables supposées indépendantes) :
   aucune approximation, aucune dépendance supplémentaire.
2. **Expliquer une décision.** Trace de la règle D9/D10/D14 qui a produit la priorité.
3. **Contrôler le modèle.** Confronter ce qu'il a appris à ce que l'on sait du domaine :
   variable exclue présente, effet de sens contraire à l'attendu, variable qui porte l'essentiel
   de l'explication (signature de fuite), modalités ou valeurs inconnues du dictionnaire.
   Un écart ne prouve pas une erreur : il la rend visible, et oblige à l'examiner.

Limites (à rappeler avec chaque explication) : une contribution décrit ce que le modèle a
appris, pas une cause ; elle est relative à un compte de référence (la moyenne du train) ; entre
variables corrélées, le partage des contributions est instable.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

CHEMIN_BASE_DEFAUT = Path(__file__).resolve().parents[1] / "knowledge" / "base_connaissance.yaml"
NOM_FICHIER_REFERENCE = "explication_reference.json"
ORDRE_GRAVITE = {"bloquant": 0, "avertissement": 1, "information": 2}
COLONNES_ANOMALIES = ["controle", "variable", "gravite", "constat"]


def charger_base_connaissance(chemin: Path | str | None = None) -> dict:
    """Lit la base de connaissance YAML (par défaut `knowledge/base_connaissance.yaml`)."""
    with open(chemin or CHEMIN_BASE_DEFAUT, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# --------------------------------------------------------------------------------------
# 1. Décomposition exacte du score
# --------------------------------------------------------------------------------------

def _decomposer(pipeline):
    """(préparation, modèle linéaire) d'un pipeline `ColumnTransformer` -> classifieur linéaire."""
    etapes = getattr(pipeline, "steps", None)
    if not etapes or len(etapes) != 2 or not isinstance(etapes[0][1], ColumnTransformer):
        raise TypeError("Pipeline attendu : [préparation ColumnTransformer, modèle]")
    preparation, modele = etapes[0][1], etapes[1][1]
    coef = getattr(modele, "coef_", None)
    if coef is None or np.ndim(coef) != 2 or coef.shape[0] != 1:
        raise TypeError("Décomposition exacte réservée à un classifieur linéaire binaire (coef_)")
    return preparation, modele


def _dense(matrice) -> np.ndarray:
    return np.asarray(matrice.toarray() if hasattr(matrice, "toarray") else matrice, dtype=float)


def _etapes(transformeur) -> list:
    return [e for _, e in transformeur.steps] if isinstance(transformeur, Pipeline) else [transformeur]


def _structure(preparation) -> dict:
    """Relie chaque colonne transformée à sa variable d'origine, et relève le type de chaque
    variable, les modalités apprises et les valeurs d'imputation."""
    variable_par_colonne: list[str] = []
    types: dict[str, str] = {}
    modalites: dict[str, list[str]] = {}
    imputation: dict[str, float] = {}

    for nom, transformeur, colonnes in preparation.transformers_:
        colonnes = list(colonnes)
        if transformeur == "drop" or not colonnes:
            continue
        if transformeur == "passthrough":
            variable_par_colonne += colonnes
            types.update({c: "numerique" for c in colonnes})
            continue

        etapes = _etapes(transformeur)
        encodeur = next((e for e in etapes if isinstance(e, OneHotEncoder)), None)
        imputeur = next((e for e in etapes if isinstance(e, SimpleImputer)), None)
        if imputeur is not None and imputeur.strategy == "median" and encodeur is None:
            imputation.update({c: float(v) for c, v in zip(colonnes, imputeur.statistics_)})

        if encodeur is not None:
            drop_idx = getattr(encodeur, "drop_idx_", None)
            for i, colonne in enumerate(colonnes):
                categories = [str(c) for c in encodeur.categories_[i]]
                n = len(categories) - (0 if drop_idx is None or drop_idx[i] is None else 1)
                variable_par_colonne += [colonne] * n
                types[colonne] = "categorielle"
                modalites[colonne] = categories
        else:
            for sortie in transformeur.get_feature_names_out(colonnes):
                if sortie in colonnes:
                    variable_par_colonne.append(sortie)
                elif sortie.startswith("missingindicator_"):
                    variable_par_colonne.append(sortie.removeprefix("missingindicator_"))
                else:
                    raise ValueError(f"Colonne transformée non reconnue : {sortie}")
            types.update({c: "numerique" for c in colonnes})

    if len(variable_par_colonne) != len(preparation.get_feature_names_out()):
        raise ValueError("Correspondance colonnes transformées -> variables incohérente")
    return {"variable_par_colonne": variable_par_colonne, "types": types,
            "modalites": modalites, "imputation": imputation}


def reference_explication(pipeline, X_reference: pd.DataFrame) -> dict:
    """Référence des contributions, calculée UNE fois sur le jeu d'entraînement du modèle et
    figée à côté de lui (`explication_reference.json`) : en production, le jeu d'entraînement
    n'est pas disponible. Contient la moyenne de chaque colonne transformée (pour une
    catégorielle : la fréquence de chaque modalité), le logit du compte de référence, la
    moyenne de chaque variable numérique (valeur affichée à côté de celle du compte)."""
    preparation, modele = _decomposer(pipeline)
    structure = _structure(preparation)
    moyennes = _dense(preparation.transform(X_reference)).mean(axis=0)
    utilisees = set(structure["variable_par_colonne"])
    variables = [v for v in preparation.feature_names_in_ if v in utilisees]
    numeriques = [v for v in variables if structure["types"][v] == "numerique"]
    valeurs = X_reference[numeriques].astype(float).fillna(pd.Series(structure["imputation"], dtype=float))
    return {
        "variables": variables,
        "types": {v: structure["types"][v] for v in variables},
        "colonnes_transformees": [str(c) for c in preparation.get_feature_names_out()],
        "variable_par_colonne": structure["variable_par_colonne"],
        "moyennes_transformees": [float(m) for m in moyennes],
        "logit_reference": float(modele.intercept_[0] + moyennes @ modele.coef_[0]),
        "moyennes_variables": {v: float(valeurs[v].mean()) for v in numeriques},
        "valeurs_imputation": structure["imputation"],
        "modalites_apprises": structure["modalites"],
        "n_reference": int(len(X_reference)),
    }


def contributions(pipeline, X: pd.DataFrame, reference: dict) -> pd.DataFrame:
    """Contribution de chaque variable au logit du score de chaque compte (en log-odds :
    positif = augmente le risque). Exact : `reference["logit_reference"]` + somme d'une ligne
    = `pipeline.decision_function(X)` pour ce compte."""
    preparation, modele = _decomposer(pipeline)
    if [str(c) for c in preparation.get_feature_names_out()] != reference["colonnes_transformees"]:
        raise ValueError("Référence d'explication incompatible avec ce modèle (colonnes différentes)")
    ecarts = _dense(preparation.transform(X)) - np.asarray(reference["moyennes_transformees"])
    par_colonne = ecarts * modele.coef_[0]
    variables = reference["variables"]
    agregation = np.zeros((len(reference["variable_par_colonne"]), len(variables)))
    for i, v in enumerate(reference["variable_par_colonne"]):
        agregation[i, variables.index(v)] = 1.0
    return pd.DataFrame(par_colonne @ agregation, index=X.index, columns=variables)


def parts_explication(contrib: pd.DataFrame) -> pd.Series:
    """Part de chaque variable dans l'explication totale d'un jeu de comptes (moyenne des
    |contributions|, normalisée à 1), triée par ordre décroissant."""
    moyenne_abs = contrib.abs().mean()
    return (moyenne_abs / moyenne_abs.sum()).sort_values(ascending=False)


def effets_lineaires(pipeline, reference: dict) -> dict[str, float]:
    """Coefficient appris pour chaque variable numérique codée sur une seule colonne (sur
    variables standardisées : effet d'une hausse d'un écart-type sur le logit)."""
    _, modele = _decomposer(pipeline)
    effets = {}
    for v in reference["variables"]:
        indices = [i for i, w in enumerate(reference["variable_par_colonne"]) if w == v]
        if reference["types"][v] == "numerique" and len(indices) == 1:
            effets[v] = float(modele.coef_[0][indices[0]])
    return effets


# --------------------------------------------------------------------------------------
# 2. Explication d'un compte et de sa décision, en langage métier
# --------------------------------------------------------------------------------------

def _manquante(valeur) -> bool:
    return valeur is None or (isinstance(valeur, float) and math.isnan(valeur)) or valeur is pd.NA


def _nombre(x: float, decimales: int = 0) -> str:
    return f"{x:,.{decimales}f}".replace(",", " ").replace(".", ",")


def _texte_valeur(valeur, fiche: dict, decimales_min: int = 0) -> str:
    if _manquante(valeur):
        return "valeur manquante"
    if fiche.get("type") == "categorielle" or isinstance(valeur, str):
        return str(valeur)
    texte = _nombre(float(valeur), max(fiche.get("decimales", 2), decimales_min))
    unite = fiche.get("unite", "")
    if not unite:
        return texte
    return f"{texte}{unite}" if unite.startswith("/") else f"{texte} {unite}"


def _valeur_json(valeur):
    if _manquante(valeur):
        return None
    return valeur if isinstance(valeur, str) else float(valeur)


def avertissements_entree(x: pd.Series, reference: dict, base: dict) -> list[str]:
    """Valeurs d'entrée qui fragilisent l'explication : manquante (remplacée par la médiane
    d'entraînement), hors de la plage du dictionnaire de données, modalité inconnue du modèle."""
    fiches = base.get("variables", {})
    avertissements = []
    for v in reference["variables"]:
        fiche, valeur = fiches.get(v, {}), x.get(v)
        libelle = fiche.get("libelle", v)
        if reference["types"][v] == "categorielle":
            if _manquante(valeur) or str(valeur) not in reference["modalites_apprises"].get(v, []):
                avertissements.append(f"{libelle} : modalité « {_texte_valeur(valeur, fiche)} » inconnue du "
                                      "modèle, aucune modalité apprise ne s'applique.")
            continue
        if _manquante(valeur):
            remplacement = reference["valeurs_imputation"].get(v)
            suite = f", remplacée par la médiane d'entraînement ({_texte_valeur(remplacement, fiche)})" \
                if remplacement is not None else ""
            avertissements.append(f"{libelle} : valeur manquante{suite}.")
        elif "plage" in fiche and not (fiche["plage"][0] <= float(valeur) <= fiche["plage"][1]):
            bas, haut = (_texte_valeur(b, fiche) for b in fiche["plage"])
            avertissements.append(f"{libelle} : valeur {_texte_valeur(valeur, fiche)} hors de la plage du "
                                  f"dictionnaire [{bas} ; {haut}], à vérifier.")
    return avertissements


def expliquer_compte(x: pd.Series, contrib: pd.Series, reference: dict, base: dict, n: int = 3) -> dict:
    """Les `n` variables qui augmentent le plus le risque du compte et les `n` qui le diminuent
    le plus, formulées avec les libellés de la base de connaissance, plus les avertissements
    sur ses valeurs d'entrée."""
    fiches = base.get("variables", {})

    def facteur(v: str) -> dict:
        fiche, valeur, c = fiches.get(v, {}), x.get(v), float(contrib[v])
        moyenne = reference["moyennes_variables"].get(v)
        texte = f"{fiche.get('libelle', v)} : {_texte_valeur(valeur, fiche)}"
        if _manquante(valeur) and v in reference["valeurs_imputation"]:
            texte += f", remplacée par {_texte_valeur(reference['valeurs_imputation'][v], fiche)}"
        elif moyenne is not None:   # une décimale de plus : « 3 (moyenne 2,6) », pas « 3 (moyenne 3) »
            texte += f" (moyenne {_texte_valeur(moyenne, fiche, fiche.get('decimales', 2) + 1)})"
        texte += ", augmente le risque" if c > 0 else ", diminue le risque"
        return {"variable": v, "libelle": fiche.get("libelle", v), "valeur": _valeur_json(valeur),
                "moyenne": moyenne, "contribution": round(c, 4), "texte": texte}

    ordre = contrib.sort_values()
    return {
        "facteurs_hausse": [facteur(v) for v in ordre[ordre > 0].index[::-1][:n]],
        "facteurs_baisse": [facteur(v) for v in ordre[ordre < 0].index[:n]],
        "avertissements": avertissements_entree(x, reference, base),
    }


def expliquer_decision(ligne: pd.Series, seuil_d9: float, capacite_haute: int, nb_signales: int) -> str:
    """Trace de la règle qui a produit la priorité d'un compte (ligne de `assigner_priorites`)."""
    score, seuil = _nombre(ligne["score_churn"], 3), _nombre(seuil_d9, 4)
    if ligne["priorite"] == "Basse":
        return f"Priorité Basse : probabilité de churn {score}, sous le seuil de signalement D9 ({seuil})."
    rang, perte = int(ligne["rang_perte_attendue"]), _nombre(ligne["perte_attendue_eur"], 0)
    signales = "compte signalé" if nb_signales == 1 else "comptes signalés"
    position = f"perte attendue {perte} €, rang {rang} sur {nb_signales} {signales}"
    if ligne["priorite"] == "Haute":
        return (f"Priorité Haute : probabilité {score} ≥ seuil D9 ({seuil}) ; {position}, "
                f"dans la capacité de {capacite_haute} comptes (D10, D14).")
    return (f"Priorité Moyenne : probabilité {score} ≥ seuil D9 ({seuil}), mais {position}, "
            f"au-delà de la capacité de {capacite_haute} comptes en priorité Haute (D10, D14).")


def expliquer_batch(pipeline, X: pd.DataFrame, resultats: pd.DataFrame, reference: dict, base: dict,
                    seuil_d9: float, capacite_haute: int, n: int = 3) -> list[dict]:
    """Une explication par compte (score + décision), dans l'ordre de `resultats` (sortie de
    `src.scoring.assigner_priorites` sur le même `X`)."""
    contrib = contributions(pipeline, X, reference)
    nb_signales = int(resultats["signale_D9"].sum())
    explications = []
    for i in range(len(X)):
        explication = expliquer_compte(X.iloc[i], contrib.iloc[i], reference, base, n)
        explication["decision"] = expliquer_decision(resultats.iloc[i], seuil_d9, capacite_haute, nb_signales)
        explications.append(explication)
    return explications


# --------------------------------------------------------------------------------------
# 3. Contrôles : le modèle est-il conforme à ce que l'on sait ?
# --------------------------------------------------------------------------------------

def _anomalie(controle: str, variable: str, gravite: str, constat: str) -> dict:
    return {"controle": controle, "variable": variable, "gravite": gravite, "constat": constat}


def controler_exclusions(features: list[str], base: dict) -> list[dict]:
    """Variables exclues (fuite, cible, identifiant, leurre...) retrouvées dans le modèle."""
    gravites = base["controles"]["gravite_exclusion"]
    anomalies = []
    for v in features:
        if v in base.get("exclusions", {}):
            e = base["exclusions"][v]
            anomalies.append(_anomalie("exclusion", v, gravites.get(e["categorie"], "bloquant"),
                                       f"Variable exclue ({e['categorie']}) présente dans le modèle : {e['raison']}"))
    return anomalies


def controler_couverture(features: list[str], base: dict) -> list[dict]:
    """Variables du modèle inconnues de la base : ni libellé, ni sens attendu, ni plage."""
    connues = set(base.get("variables", {})) | set(base.get("exclusions", {}))
    return [_anomalie("couverture", v, "avertissement",
                      "Variable absente de la base de connaissance : explication en langage métier et "
                      "contrôle de sens impossibles.")
            for v in features if v not in connues]


def controler_sens(effets: dict[str, float], base: dict) -> list[dict]:
    """Effets appris de sens contraire au sens attendu (fixé a priori dans la base)."""
    gravite = base["controles"].get("gravite_sens_contraire", "avertissement")
    anomalies = []
    for v, effet in effets.items():
        sens = base.get("variables", {}).get(v, {}).get("sens_attendu")
        attendu = {"hausse": 1, "baisse": -1}.get(sens)
        if attendu is not None and effet != 0 and np.sign(effet) != attendu:
            anomalies.append(_anomalie("sens", v, gravite,
                                       f"Effet appris de sens contraire à l'attendu ({sens} du risque "
                                       f"attendue, coefficient {effet:+.3f})."))
    return anomalies


def controler_concentration(parts: pd.Series, base: dict) -> list[dict]:
    """Une seule variable porte plus que la part maximale admise de l'explication."""
    seuil = base["controles"]["part_max_une_variable"]
    gravite = base["controles"].get("gravite_concentration", "bloquant")
    return [_anomalie("concentration", v, gravite,
                      f"La variable porte {p:.0%} de l'explication totale (maximum admis {seuil:.0%}) : "
                      "signature possible d'une fuite de données.")
            for v, p in parts.items() if p > seuil]


def controler_modalites(reference: dict, base: dict) -> list[dict]:
    """Modalités apprises absentes du dictionnaire (nettoyage à revoir ?) et modalités du
    dictionnaire jamais vues à l'entraînement."""
    anomalies = []
    for v, apprises in reference["modalites_apprises"].items():
        fiche = base.get("variables", {}).get(v, {})
        if "modalites" not in fiche:
            continue
        connues = set(fiche["modalites"]) | set(fiche.get("modalites_ajoutees_par_nettoyage", []))
        inconnues = sorted(set(apprises) - connues)
        jamais_vues = sorted(set(fiche["modalites"]) - set(apprises))
        if inconnues:
            anomalies.append(_anomalie("modalites", v, "avertissement",
                                       f"Modalités apprises absentes du dictionnaire : {', '.join(inconnues)}."))
        if jamais_vues:
            anomalies.append(_anomalie("modalites", v, "information",
                                       f"Modalités du dictionnaire jamais vues à l'entraînement : {', '.join(jamais_vues)}."))
    return anomalies


def controler_modele(features: list[str], base: dict, pipeline=None, reference: dict | None = None,
                     X: pd.DataFrame | None = None) -> pd.DataFrame:
    """Tous les contrôles applicables, du plus grave au moins grave. Avec les seules `features`
    (modèle quelconque) : exclusions et couverture ; avec un pipeline linéaire et sa
    `reference` : sens et modalités ; avec en plus un jeu `X` : concentration."""
    anomalies = controler_exclusions(features, base) + controler_couverture(features, base)
    if pipeline is not None and reference is not None:
        anomalies += controler_sens(effets_lineaires(pipeline, reference), base)
        anomalies += controler_modalites(reference, base)
        if X is not None:
            anomalies += controler_concentration(parts_explication(contributions(pipeline, X, reference)), base)
    table = pd.DataFrame(anomalies, columns=COLONNES_ANOMALIES)
    return (table.assign(_ordre=table["gravite"].map(ORDRE_GRAVITE))
            .sort_values(["_ordre", "controle"], kind="stable").drop(columns="_ordre").reset_index(drop=True))


def attribuer_derive(contrib_reference: pd.DataFrame, contrib_courant: pd.DataFrame) -> pd.DataFrame:
    """Décompose l'écart de logit moyen entre deux jeux de comptes, variable par variable :
    quelles variables font monter (ou baisser) les scores du jeu courant ? Exact : la somme de
    la colonne `ecart` = écart des logits moyens des deux jeux."""
    table = pd.DataFrame({"contribution_moyenne_reference": contrib_reference.mean(),
                          "contribution_moyenne_courante": contrib_courant.mean()})
    table["ecart"] = table["contribution_moyenne_courante"] - table["contribution_moyenne_reference"]
    return table.reindex(table["ecart"].abs().sort_values(ascending=False).index)
