---
type: référence
statut: à jour
mise_a_jour: 2026-09-29
sources: bronze_manifest.json, gold_v2_manifest.json, fichiers *.csv.dvc, notebook §3
---

[← Documentation](../index.md)

# Sources de données

## Les trois fichiers fournis

| Fichier | Contenu | Lignes brutes | Usage |
|---|---|---|---|
| `churn_saas_complet.csv` | Comptes clients : usage, facturation, support, contrat, deux cibles (29 colonnes) | 5 035 (5 000 après suppression de 35 doublons) | Entraînement et évaluation |
| `churn_saas_echantillon.csv` | 50 comptes, même format | 50 | Simulation d'un export brut à scorer (notebook §10.3) |
| `catalogue_plans.csv` | 4 plans tarifaires (prix par siège, SLA, quota…) | 4 | Jointure sur `plan` |

Les données sont **réalistes et volontairement imparfaites** (énoncé, §2) : valeurs manquantes,
nombres stockés en texte (%, €, virgules décimales), casse hétérogène, dates en formats multiples,
doublons, variables leurres et une variable de fuite. Le traitement de chaque défaut est décrit
dans [Préparation des données](preparation.md) ; la signification de chaque colonne dans le
[dictionnaire](dictionnaire.md).

## Identité exacte des fichiers

| Fichier | SHA-256 (manifestes) | MD5 (DVC) |
|---|---|---|
| `churn_saas_complet.csv` | `2fc45e8c3c74d3ddcdbda162c5bb50184587201b46d877cc06742afd13063844` | `2b44e1405bf6a5c13cc71652cc90cf34` |
| `churn_saas_echantillon.csv` | `680f5371c406f47a3a67f1611cb016c17efd61e93a52d1b4b8dbd3a39dc2f296` | `30c65edbe30ae1616cc930223d25678c` |
| `catalogue_plans.csv` | `c94f6f52652532c578cb7a44d752b8b197ef84f5e6c6e17a58579fa195e9ad08` | `6e1d25ff7514ef0766625891ac1dac57` |

Le SHA-256 est écrit par les notebooks dans les manifestes
([`bronze_manifest.json`](../../data/bronze/bronze_manifest.json),
[`gold_v2_manifest.json`](../../data/gold/gold_v2_manifest.json)) : il **prouve** quelle version a
produit quel résultat. Le MD5 est celui qu'utilise DVC pour **détecter** un changement
([`*.csv.dvc`](../../Examen_cas%20d'usage%20candidat/churn_saas_complet.csv.dvc)).

## Où les trouver

| Accès | Lien | Compte requis |
|---|---|---|
| Release GitHub v2.0 (archive des données et des modèles) | https://github.com/guillaumesaidani-coder/churn_saas/releases/tag/v2.0 | Non |
| Stockage DVC sur DagsHub | https://dagshub.com/guillaume.saidani/churn_saas | Oui (gratuit) pour naviguer |
| Depuis un clone du dépôt | `dvc pull` | Jeton DagsHub |

Git ne contient que les empreintes (`*.dvc`, `dvc.lock`) ; les fichiers eux-mêmes sont stockés sur
DagsHub. L'énoncé (PDF) et les supports fournis par la formation ne sont pas publiés.

## Alternatives envisagées (notebook §3.3)

| Alternative | Décision | Raison |
|---|---|---|
| Base PostgreSQL pour la couche Silver | Écartée | Non exigée ; le notebook doit s'exécuter sans serveur ; Parquet typé + manifestes couvre le besoin |
| Données externes (sectorielles, tickets détaillés, logs d'usage) | Non disponibles | Piste d'amélioration : des logs datés permettraient des tendances d'usage |
| Historique multi-périodes | Non disponible | Limite majeure : pas de validation temporelle possible |

Voir aussi : [pipeline et lignage](pipeline_et_lignage.md) · [RGPD et éthique](rgpd_et_ethique.md)
