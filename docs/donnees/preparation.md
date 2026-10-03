---
type: explication
statut: à jour
mise_a_jour: 2026-10-03
sources: notebook §6 et §7 ; src/silver.py, src/features.py, src/gold.py ; gold_fiche_identite_v2.md
---

[← Documentation](../index.md)

# Préparation des données (Gold v2)

Chaque transformation est une fonction de `src/`, couverte par des tests unitaires. La même
logique sert à l'entraînement et au scoring d'un export brut : aucun écart possible entre les
données vues à l'entraînement et celles reçues en production.

## Nettoyage (Bronze → Silver, [`src/silver.py`](../../src/silver.py))

| Défaut du fichier brut | Traitement | Résultat |
|---|---|---|
| Doublons stricts | Suppression | 35 doublons supprimés : 5 035 → 5 000 comptes |
| Dates en formats multiples | Analyse multi-format | 0 date illisible |
| Nombres stockés en texte (%, €, unités, virgules) | Conversion dédiée (le bug de la conversion naïve est démontré au notebook §7) | Colonnes numériques typées |
| Casse et espaces hétérogènes des catégories | Normalisation | Secteurs harmonisés |
| Jointure avec le catalogue des plans | Sur `plan` | 0 compte orphelin |

## Valeurs manquantes : une décision par colonne (notebook §7.6)

| Colonne(s) | Manquants | Traitement | Justification |
|---|---|---|---|
| `revenu_mensuel_recurrent_eur` | 3 % | **Approché** : sièges × prix catalogue du plan | Approximation sans remise : le revenu réel vaut 0,6 à 1,5 fois le prix catalogue (notebook §6.5) |
| `taux_adoption_pct` | 5 % | **Recalculé** : 100 × actifs / sièges | Définition même de la variable |
| `secteur`, `pays` | quelques % | Modalité explicite « Inconnu » | Ne pas inventer une catégorie ; l'absence reste visible |
| `heures_usage_30j`, `nb_integrations`, `delai_reponse_support_h`, `csat`, `retards_paiement_12m` | 4 à 10 % | **Médiane apprise sur le seul jeu d'entraînement**, dans le pipeline du modèle | Robuste aux valeurs extrêmes ; aucune information du test utilisée |
| `commentaire_csm` | 55 % vides | Non traité | Colonne exclue ([D7](../cadrage/decisions/D07.md)) |

L'imputation par la médiane fait partie du **pipeline sérialisé** : une valeur manquante reçue par
l'API est remplacée par la même médiane qu'à l'entraînement, et l'explication du compte le signale
([lire une explication](../explicabilite/lire_une_explication.md)).

## Valeurs incohérentes : 13 règles de cohérence (notebook §6.5, v2.1)

| Règle | Comptes en infraction | Traitement | Justification |
|---|---|---|---|
| `retards_paiement_12m` ≤ min(`anciennete_mois`, 12), nombre de mois facturés sur la fenêtre (facturation mensuelle) | **449 (9 %)**, dont 419 à 1 mois d'ancienneté (jusqu'à 7 retards), 61 % de churn | **Neutralisée en valeur manquante**, puis médiane du train comme les autres manquants ; `taux_retard_paiement_par_mois` suit le même sort | Valeur impossible et liée à la cible |
| 12 autres règles | 0 | Aucun : les valeurs extrêmes sont conservées | Aucune incohérence |

La neutralisation est faite par `neutraliser_incoherences` ([`src/features.py`](../../src/features.py)),
appelée par `construire_features_v2` (entraînement et scoring d'un export brut) et par l'API avant
le modèle. Trois données sont conservées **avec réserve** : les connexions et heures d'usage ne
croissent pas avec la taille du compte (indice d'intensité, pas un volume) ; le délai de réponse
du support est renseigné pour 1 177 comptes sans ticket (23,5 %) ; la CLV est plafonnée
(154 comptes à 300 €, 14 à 2 000 000 €).

## Variables du modèle ([`src/features.py`](../../src/features.py))

**20 variables** : 3 catégorielles (`secteur`, `taille_entreprise`, `plan`) et 17 numériques, dont
2 ratios construits. Détail de chaque colonne dans le [dictionnaire](dictionnaire.md).

| Exclusion | Colonnes | Raison |
|---|---|---|
| Identifiant | `client_id` | Aucune valeur prédictive légitime |
| Redondante | `date_souscription` | Information portée par `anciennete_mois` |
| Conformité | `commentaire_csm` | Minimisation : 13 phrases types sans apport (ablation 0,780 contre 0,783) ; un texte libre peut contenir des noms en production ([D7](../cadrage/decisions/D07.md)) |
| **Fuite de données** | `sante_compte_fin_periode` | Calculée en fin de période, donc indisponible au scoring : AUC univariée de **0,999** |
| Cible secondaire | `valeur_vie_client_eur` | Interdite comme variable du churn (énoncé §3.2) |
| Leurres | `jour_souscription`, `pays`, `code_datacenter`, `couleur_theme_interface`, `groupe_experimentation` | Aucun effet mesurable sur le churn (test statistique, notebook §6) |
| Redondantes (catalogue) | `prix_mensuel_par_siege_eur`, `fonctionnalites_incluses`, `sla_reponse_h`, `quota_stockage_go`, `support_dedie` | Une seule valeur par plan : répètent `plan` |

`sieges_souscrits` est signalée par le test des leurres mais **conservée** : c'est une variable
métier centrale (taille du contrat), elle porte l'information de la régression CLV et l'ablation
montre que la garder ne dégrade rien (notebook §8.4).

## Découpage entraînement / test

80 % / 20 % stratifié sur `churn`, graine 42 : 4 000 comptes d'entraînement et 1 000 de test,
28,0 % de churn dans chacun. Le découpage est **identique à celui de la v1**, ce qui permet de
comparer les deux versions compte par compte. **Aucun choix de variable, de modèle,
d'hyperparamètre ni de seuil n'utilise le test** : il mesure le modèle final, puis sert à des
analyses descriptives. Il a été lu une seconde fois, de façon assumée, pour mesurer la révision
v2.1 (notebook §9.3, [protocole](../modeles/protocole_experimental.md)).

## Ce qui change par rapport au Gold v1

- 5 leurres et 5 colonnes du catalogue exclus : 30 → 20 variables, pour une performance identique
  (ablation, notebook §8.4).
- Médianes d'imputation calculées **dans le pipeline, sur le seul entraînement**. La v1 les
  calculait sur les 5 000 comptes avant le découpage : une fuite minime mais réelle, corrigée.
- `taux_adoption_pct` recalculé au lieu d'être imputé.
- v2.1 : retards de paiement impossibles neutralisés en valeur manquante (voir plus haut).

Voir aussi : [pipeline et lignage](pipeline_et_lignage.md) ·
[fiche d'identité du Gold v2](../../data/gold/gold_fiche_identite_v2.md)
