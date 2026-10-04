---
type: explication
statut: à jour
mise_a_jour: 2026-10-03
sources: notebook §1, §2.7, §8 (dont §8.5 et §8.6) et §9 (dont §9.8)
---

[← Documentation](../index.md)

# Protocole expérimental

Comment le modèle a été choisi, réglé et évalué, sans que le jeu de test influence aucun choix.

## Règle centrale : aucun choix n'utilise le test

Le jeu de test (20 % des comptes, 1 000) est mis de côté **dès la préparation** : **aucun choix de
variable, de modèle, d'hyperparamètre ni de seuil n'utilise le test**. Tous sont faits en
**validation croisée sur le seul jeu d'entraînement** (4 000 comptes). Le test mesure ensuite le
modèle final (notebook §9.3), puis sert à des analyses descriptives (calibration, explicabilité,
impact, équité), qui ne modifient aucun choix.

> [!NOTE]
> C'est une **correction de la v1**, qui choisissait le modèle et calibrait le seuil sur le jeu de
> test : ses mesures étaient optimistes par construction.

> [!WARNING]
> **Révision v2.1 : seconde lecture assumée du test** (notebook §9.3). La neutralisation des
> retards de paiement impossibles a été décidée sur un critère de qualité des données (notebook
> §6.5), pas sur le score ; le test a ensuite été relu une seconde fois pour mesurer le modèle v2.1.

## Étapes

| Étape | Méthode | Où |
|---|---|---|
| Métrique principale | **PR-AUC**, plus informative que la ROC-AUC quand la classe d'intérêt est minoritaire (28 %) ; ROC-AUC en complément (exigée par l'énoncé) ; jamais l'exactitude seule | §6, §8.1 |
| Validation | Validation croisée **stratifiée à 5 plis**, graine 42 : moyenne **et** dispersion de chaque score | §8.1 |
| Références à battre | Baseline naïve (PR-AUC ≈ 0,28) et **baseline métier** [D8](../cadrage/decisions/D08.md), reformulée sans la variable de fuite ; sensibilité à une règle enrichie de la satisfaction (CSAT) | §8.2, §8.4 |
| Familles comparées | Régression logistique, forêt aléatoire, gradient boosting ; forêt et boosting aussi **réglés** par recherche sur grille | §8.3 |
| Règle de sélection, **fixée à l'avance** | Le meilleur score moyen, sauf si un modèle plus simple et plus explicable fait jeu égal (écart inférieur à un écart-type) ; appliquée par le code | §8.1 |
| Ablation | Retirer ou ajouter des groupes de variables pour justifier le Gold v2 ; `commentaire_csm`, logarithme des variables de taille, splines | §8.4 |
| Réglage | Recherche sur grille de la régularisation `C` en validation croisée | §9.1 |
| Seuil de décision | Calculé sur des **prédictions hors pli** de l'entraînement ([D9](../cadrage/decisions/D09.md)) | §9.2 |
| Évaluation finale | Sur le test : PR-AUC, ROC-AUC, matrices de confusion, critère D8 avec son intervalle de confiance | §9.3, §12.1 |
| Calibration | Courbe de calibration, score de Brier, ECE ; recalibration (Platt, isotonique) comparée, non retenue | §9.4 |
| Explicabilité | Coefficients, importance par permutation, contrôles par la base de connaissance | §9.6 |
| Choix vu de la décision | Perte captée par les appels à **capacité proportionnelle** (3 % et 15 %), prédictions hors pli sur l'entraînement, intervalles bootstrap ; comparaison à l'oracle | §9.8 |

## Résultats du choix

- Les trois familles battent largement les deux baselines ; la **régression logistique** obtient
  le meilleur score moyen. Les modèles plus complexes n'apportent rien : la relation entre signaux
  d'engagement et churn est essentiellement linéaire (au sens du logit). Le modèle le plus simple
  est aussi le plus performant et le plus explicable.
- **Ablation** : retirer les 5 leurres et les 5 colonnes redondantes ne coûte rien (30 → 20
  variables, même score). Des indicateurs de valeur manquante et d'autres ratios ont été testés :
  ils n'apportent rien et ne sont pas retenus. Retirer `sieges_souscrits` est neutre.
  v2.1 : conserver les retards impossibles (v2.0) donnait 0,791 contre 0,783, écart inférieur à un
  écart-type ; l'indicateur « retards manquants » seul donne 0,786 mais réintroduirait le défaut :
  non retenu.
- **Régularisation** : `C = 0,03`, sur une courbe plate autour de l'optimum ; le modèle est
  robuste à ce choix.
- **Concurrents réglés** : une recherche sur grille porte la forêt à 0,770 et le boosting à 0,774,
  toujours sous la régression logistique (0,783).
- **Autres ablations** : `commentaire_csm` (13 phrases types) donne 0,780 contre 0,783 sans ; le
  logarithme des variables de taille 0,769 ; des splines 0,781. Aucun n'apporte rien
  ([D7](../cadrage/decisions/D07.md)).
- **Sensibilité de D8** : une règle métier qui ajoute la satisfaction (CSAT) atteint 0,674 en
  validation croisée ; l'écart du modèle tombe à +0,109. Sur le test, le gain de +0,154 sur la règle
  D8 a un intervalle de confiance à 95 % de +0,108 à +0,202 ([D8](../cadrage/decisions/D08.md)).
- **Pas de pondération des classes** : `class_weight="balanced"` ne change ni la ROC-AUC ni la
  PR-AUC ; il déplace seulement le point de fonctionnement, ce que le seuil D9 fait déjà. Les deux
  leviers sont redondants ; on garde le seuil, plus simple à expliquer et à faire varier sans
  réentraîner.

Chiffres détaillés : [model card churn v2](model_card_churn_v2.md) et
[model card CLV v2](model_card_clv_v2.md).

## Le choix vu de la décision (notebook §9.8)

La PR-AUC juge le classement de tous les comptes par risque ; la décision n'appelle que 3 % du
portefeuille, triés par probabilité × valeur (notebook §2.7). Le choix est donc vérifié sur la
**perte captée** par les appels, sans toucher au test : prédictions hors pli des deux modèles sur
les 4 000 comptes du train, seuil D9 recalculé pour chaque modèle, capacité proportionnelle (120
appels, soit 3 % ; et 15 %), 1 000 tirages bootstrap.

| Liste d'appels, 3 % | Perte captée | Précision |
|---|---|---|
| Régression logistique, règle D14 | 47 % (IC 37 à 56 %) | 69 % |
| Forêt / boosting, règle D14 | 47 % / 46 % | |
| Règle métier D8 calibrée, règle D14 | 48 % | 40 % |
| Oracle (avenir connu) | 76 % | |

Sur la valeur captée, les modèles font jeu égal : la CLV estimée ordonne la liste (84 % des comptes
appelés sont ceux d'un tri par CLV seule). La régression logistique est retenue sur la PR-AUC, la
précision des appels, la calibration et l'explicabilité ; la perte captée ne départage pas les
modèles. Elle varie d'environ ±10 points d'un échantillon à l'autre : 1 % des comptes portent 52 %
de la perte réelle. Détail : [système de décision](systeme_de_decision.md).

## Solutions sur étagère et nature du résultat (notebook §8.5)

Trois options ont été comparées : un score intégré à un outil du marché (CRM, plateforme Customer
Success), un AutoML de fournisseur cloud, un modèle développé. Le modèle développé est retenu : le
contrôle de la fuite et le système de décision ([D9](../cadrage/decisions/D09.md),
[D10](../cadrage/decisions/D10.md), [D14](../cadrage/decisions/D14.md)) exigent un contrôle complet,
et une régression logistique suffit. La comparaison est qualitative, sans essai des produits ; un
outil du marché devrait être comparé sur le même jeu de test avant tout remplacement.

Le résultat est **probabiliste** (probabilité de résiliation, CLV estimée), rendu **déterministe**
par le système de décision : la même entrée donne toujours la même liste priorisée.

## Éco-conception (notebook §8.6)

Mesure avec CodeCarbon (hors ligne, mix électrique français), lors du rejeu officiel du notebook
v2.3 (4 octobre 2026) :

| Modèle | PR-AUC (CV) | Énergie de la sélection (mWh) | Scoring de 1 000 comptes (ms) | Taille du modèle |
|---|---|---|---|---|
| Régression logistique (retenue) | 0,783 | 2,97 | 5,2 | 4,8 Ko |
| Forêt aléatoire | 0,764 | 54,4 (**18 fois plus**) | 64,5 | 28,7 Mo |
| Gradient boosting | 0,755 | 82,2 (**28 fois plus**) | 9,9 | 1,1 Mo |

Ces valeurs varient d'une exécution à l'autre (18 et 28 fois au rejeu du 1er octobre, 17 et 26 fois
à l'exécution à blanc du 3 octobre, 17 et 28 fois au premier rejeu officiel du même jour, 17 et 27
fois au deuxième, le 4 octobre) ; l'ordre de grandeur est stable : les familles à
base d'arbres consomment **plus de dix fois** l'énergie du modèle retenu (notebook §8.6).

Le modèle retenu est aussi le plus sobre. Les valeurs absolues sont infimes et estimées : à
cette échelle, l'éco-conception tient aux choix de sobriété (pas de modèle plus lourd sans gain,
scoring mensuel, réentraînement sur déclencheur).

## Pourquoi un seuil de rappel plutôt qu'un seuil de coût minimal

Pour chaque seuil, l'analyse de coût (notebook §9.5) calcule
`coût = faux négatifs × 6 879 € + faux positifs × coût d'une relance`, avec les deux bornes de
[H01](../cadrage/hypotheses.md). Même en tenant compte du taux de succès des relances
([H05](../cadrage/hypotheses.md)), le seuil de coût minimal ferait contacter **45 à 75 % des
comptes**, bien au-delà de la capacité de l'équipe ([D10](../cadrage/decisions/D10.md)). D9 fixe
donc un objectif de rappel atteignable, et D10/D14 gèrent la capacité. Rapport de coût faux
négatif / faux positif : 46:1 à 138:1, ou 5:1 à 41:1 avec H05 ([D4](../cadrage/decisions/D04.md)).

## Reproductibilité

Graine unique (42), découpage matérialisé dans la table Gold, pipeline DVC, versions des
bibliothèques figées (`requirements*.txt`) et affichées par le notebook (§15.1). Chaque
entraînement est tracé dans MLflow avec l'empreinte du Gold utilisé.

Voir aussi : [préparation des données](../donnees/preparation.md) ·
[contrôles d'explicabilité](../explicabilite/controles.md)
