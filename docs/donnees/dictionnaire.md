---
type: référence
statut: à jour
mise_a_jour: 2026-10-03
sources: énoncé §2.1 ; knowledge/base_connaissance.yaml ; notebook §6 et §7.6
---

[← Documentation](../index.md)

# Dictionnaire de données

Toutes les colonnes du jeu principal, avec leur rôle dans le modèle v2 : **20 variables**
servent au modèle (3 catégorielles, 17 numériques dont 2 ratios construits), les autres sont
exclues pour une raison précise. Rôles et sens attendus viennent de la
[base de connaissance](../explicabilite/base_de_connaissance.md) : ce tableau en est une vue lisible,
la base reste la référence (et un test vérifie qu'elle décrit exactement les variables du modèle).

## Jeu principal (`churn_saas_complet.csv`, 29 colonnes)

| Colonne | Type | Description (énoncé §2.1) | Exemple / plage | Rôle dans le modèle v2 | Valeurs manquantes |
|---|---|---|---|---|---|
| `client_id` | texte | Identifiant unique du compte client | ex. CLI-000001 | Exclue (identifiant) : Aucune valeur prédictive légitime. | — |
| `date_souscription` | date | Date de souscription (formats mêlés) | AAAA-MM-JJ, JJ/MM/AAAA, JJ mois AAAA | Exclue (redondante) : Information portée par anciennete_mois. | — |
| `jour_souscription` | catégoriel | Jour de semaine de la souscription | lundi à dimanche | Exclue (leurre) : Aucun effet mesurable sur le churn (§6). | — |
| `secteur` | catégoriel | Secteur d'activité du client | Tech, Finance, Commerce, Santé, Industrie, Public, Éducation | **Variable du modèle** — sens attendu : indéterminé | modalité explicite « Inconnu » |
| `pays` | catégoriel | Pays de facturation | France, Espagne, Canada, Allemagne, Suisse, Belgique | Exclue (leurre) : Aucun effet mesurable (§6) ; risque de traitement différencié (§4). | modalité explicite « Inconnu » |
| `taille_entreprise` | catégoriel | Segment de taille | TPE, PME, ETI, GE | **Variable du modèle** — sens attendu : indéterminé | — |
| `plan` | catégoriel | Formule d'abonnement (référentiel catalogue) | Starter, Pro, Business, Enterprise | **Variable du modèle** — sens attendu : indéterminé | — |
| `anciennete_mois` | entier | Ancienneté du compte en mois | 1 – 36 | **Variable du modèle** — sens attendu : ↓ diminue le risque | — |
| `sieges_souscrits` | entier | Nombre de licences souscrites | 1 – 898 | **Variable du modèle** — sens attendu : indéterminé | — |
| `utilisateurs_actifs` | entier | Utilisateurs actifs (≤ sièges) | 0 – 829 | **Variable du modèle** — sens attendu : ↓ diminue le risque | — |
| `taux_adoption_pct` | décimal | Taux d'adoption (%) = actifs / sièges | 0,0 – 100,0 | **Variable du modèle** — sens attendu : ↓ diminue le risque | recalculé : 100 × actifs / sièges |
| `connexions_30j` | entier | Connexions sur 30 jours | 0 – 156 | **Variable du modèle** — sens attendu : ↓ diminue le risque | — |
| `heures_usage_30j` | décimal | Heures d'usage cumulées sur 30 jours | 0,0 – 170,4 | **Variable du modèle** — sens attendu : ↓ diminue le risque | médiane du jeu d'entraînement, dans le pipeline |
| `fonctionnalites_total` | entier | Fonctionnalités offertes par le plan | 8 – 40 | **Variable du modèle** — sens attendu : indéterminé | — |
| `fonctionnalites_utilisees` | entier | Fonctionnalités effectivement utilisées | 0 – 40 | **Variable du modèle** — sens attendu : ↓ diminue le risque | — |
| `nb_integrations` | entier | Intégrations tierces connectées | 0 – 16 | **Variable du modèle** — sens attendu : ↓ diminue le risque | médiane du jeu d'entraînement, dans le pipeline |
| `derniere_connexion_jours` | entier | Jours depuis la dernière connexion | 0 – 200 | **Variable du modèle** — sens attendu : ↑ augmente le risque | — |
| `tickets_support_90j` | entier | Tickets support sur 90 jours | 0 – 17 | **Variable du modèle** — sens attendu : ↑ augmente le risque | — |
| `delai_reponse_support_h` | décimal | Délai moyen de réponse du support (h) | 0,5 – 56,5 | **Variable du modèle** — sens attendu : ↑ augmente le risque | médiane du jeu d'entraînement, dans le pipeline |
| `csat` | entier | Satisfaction client (1 à 5) | 1 – 5 | **Variable du modèle** — sens attendu : ↓ diminue le risque | médiane du jeu d'entraînement, dans le pipeline |
| `retards_paiement_12m` | entier | Retards de paiement sur 12 mois | 0 – 7 | **Variable du modèle** — sens attendu : ↑ augmente le risque | médiane du jeu d'entraînement, dans le pipeline ; **v2.1** : valeur impossible (> min(ancienneté, 12) mois facturés, 449 comptes) neutralisée en manquante par `neutraliser_incoherences` |
| `revenu_mensuel_recurrent_eur` | décimal | Revenu mensuel récurrent (MRR, €) | 9,1 – 89 402,9 | **Variable du modèle** — sens attendu : indéterminé | recalculé : sièges × prix catalogue du plan |
| `couleur_theme_interface` | catégoriel | Thème d'interface choisi | clair, vert, bleu, violet, sombre | Exclue (leurre) : Aucun effet mesurable sur le churn (§6). | — |
| `code_datacenter` | catégoriel | Datacenter d'hébergement | eu-w3, us-e1, ap-s1, eu-w1 | Exclue (leurre) : Aucun effet mesurable sur le churn (§6). | — |
| `groupe_experimentation` | catégoriel | Groupe de test A/B | A, B, control | Exclue (leurre) : Aucun effet mesurable sur le churn (§6). | — |
| `commentaire_csm` | texte libre | Note libre du Customer Success Manager | souvent vide | Exclue (conformité (D7)) : Texte libre, risque de données personnelles (D7). | non traité (55 % vides, colonne exclue) |
| `sante_compte_fin_periode` | entier | Score de santé calculé en **fin** de période | 0 – 100 | Exclue (fuite de données) : Calculée en fin de période, après la décision (AUC univariée 0,999). | — |
| `valeur_vie_client_eur` | numérique | Valeur vie client (€) — cible secondaire | 300 – 2 000 000 | Exclue (cible secondaire) : Interdite comme variable du churn (énoncé §3.2). | — |
| `churn` | binaire | Résiliation à l'échéance (1) ou non (0) — cible principale | 0 ou 1 | Exclue (cible) : Cible du modèle. | — |

## Colonnes ajoutées par la jointure avec le catalogue

Chacune ne prend qu'une valeur par plan : elle répète l'information de `plan` (notebook §6).

| Colonne | Rôle dans le modèle v2 |
|---|---|
| `prix_mensuel_par_siege_eur` | Exclue (redondante) : Une seule valeur par plan (catalogue). |
| `fonctionnalites_incluses` | Exclue (redondante) : Une seule valeur par plan (catalogue). |
| `sla_reponse_h` | Exclue (redondante) : Une seule valeur par plan (catalogue). |
| `quota_stockage_go` | Exclue (redondante) : Une seule valeur par plan (catalogue). |
| `support_dedie` | Exclue (redondante) : Une seule valeur par plan (catalogue). |

## Variables construites (`src/gold.py::add_ratio_features`)

| Variable | Définition | Rôle dans le modèle v2 |
|---|---|---|
| `taux_utilisation_fonctionnalites` | fonctionnalités utilisées ÷ fonctionnalités offertes (0 si aucune offerte) | **Variable du modèle** — sens attendu : ↓ diminue le risque |
| `taux_retard_paiement_par_mois` | retards de paiement sur 12 mois ÷ ancienneté (au moins 1 mois) ; manquant si les retards sont neutralisés (v2.1), plage 0 – 1 | **Variable du modèle** — sens attendu : ↑ augmente le risque |

> [!NOTE]
> Les contrôles d'explicabilité ont montré que ces deux ratios n'apportent rien au modèle v2.1
> (PR-AUC en validation croisée de 0,785 avec eux, 0,784 sans ; signe instable pour le taux
> d'utilisation ; le taux de retard est stable mais fonction exacte des retards et de l'ancienneté) :
> leur retrait est recommandé pour la v3 ([contrôles](../explicabilite/controles.md)).

## Features et cible de chaque modèle

Le Gold v2 compte 25 colonnes : 20 features, 2 cibles et 3 colonnes qui n'entrent dans aucun
modèle. Les deux modèles lisent **les mêmes 20 features** (liste exacte : `FEATURES_V2`,
`src/features.py`) ; seule la préparation des numériques diffère.

| Features | Modèle de churn | Modèle de CLV |
|---|---|---|
| **3 catégorielles** : `secteur` (8 modalités : Commerce, Tech, Finance, Industrie, Éducation, Santé, Public, Inconnu), `taille_entreprise` (4 : TPE, PME, ETI, GE), `plan` (4 : Starter, Pro, Business, Enterprise) | One-hot, modalité inconnue ignorée | Idem |
| **17 numériques** : `anciennete_mois`, `sieges_souscrits`, `utilisateurs_actifs`, `taux_adoption_pct`, `connexions_30j`, `heures_usage_30j`, `fonctionnalites_total`, `fonctionnalites_utilisees`, `nb_integrations`, `derniere_connexion_jours`, `tickets_support_90j`, `delai_reponse_support_h`, `csat`, `retards_paiement_12m`, `revenu_mensuel_recurrent_eur`, `taux_utilisation_fonctionnalites`, `taux_retard_paiement_par_mois` | Médiane du train puis standardisation | Médiane du train, sans standardisation |

| | Modèle de churn | Modèle de CLV |
|---|---|---|
| Cible | `churn` | `valeur_vie_client_eur` |
| Type de problème | Classification binaire | Régression |
| Classes de la cible | **0** = reste client, **1** = résilie à l'échéance | Aucune : montant continu (300 à 2 000 000 €), appris en `log(1 + CLV)` |
| Répartition — train (4 000) | 2 880 × 0, 1 120 × 1 (28,0 %) | Médiane 11 086,5 € |
| Répartition — test (1 000) | 720 × 0, 280 × 1 (28,0 %) | Médiane 11 601,5 € |
| Déséquilibre | Classes non pondérées ([protocole](../modeles/protocole_experimental.md)) ; mesure par la PR-AUC | Distribution très étirée, d'où le log |

Colonnes du Gold qui n'entrent dans aucun modèle : `client_id` (identifiant), `split`
(train / test, graine 42, stratifié sur `churn`), `sante_compte_fin_periode` (fuite, conservée
pour traçabilité). Chaque cible est absente de l'autre modèle : la CLV ne doit pas servir à
prédire le churn (énoncé §3.2), et le churn n'entre pas dans la CLV.

## Sens attendu

Le **sens attendu** est l'effet qu'on attend d'une hausse de la variable sur le risque de churn,
fixé à partir du métier et de l'analyse exploratoire **avant** d'entraîner le modèle.
« Indéterminé » signifie qu'aucune hypothèse n'est défendable a priori : la variable n'est alors
pas soumise au contrôle de sens.

Voir aussi : [sources](sources.md) · [préparation des données](preparation.md)
