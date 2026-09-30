---
type: explication
statut: à jour
mise_a_jour: 2026-09-29
sources: src/explain.py ; notebook §9.6, §10.2.1 et §13.1.1
---

[← Documentation](../index.md)

# Méthode d'explication

## Deux niveaux d'explication

| Niveau | Question | Méthode | Où |
|---|---|---|---|
| **Global** | Quelles variables pèsent sur le risque en général ? | Coefficients de la régression logistique ; importance par permutation (baisse de PR-AUC quand on mélange une variable) | Notebook §9.6 |
| **Local** | Pourquoi **ce** compte a-t-il ce score, et cette priorité ? | Contributions exactes au score ; trace de la règle de décision | Notebook §10.2.1, API `?explain=true` |

## Décomposer un score, exactement

Pour une régression logistique, le logit du score (logarithme du rapport de chances) est une
somme : constante + Σ coefficient × valeur transformée. On le réécrit par rapport à un **compte
de référence**, la moyenne du jeu d'entraînement :

```text
logit(compte) = logit(référence) + Σ contributions
contribution  = coefficient × (valeur transformée − valeur de référence)
```

- Une contribution **positive** augmente le risque ; une contribution **négative** le diminue.
- Pour une variable numérique, la valeur transformée est la valeur imputée puis standardisée ; pour
  une catégorielle, les colonnes one-hot de la variable sont regroupées et la référence est la
  fréquence de chaque modalité dans le jeu d'entraînement.
- La décomposition est **exacte** : l'écart mesuré sur les 1 000 comptes du test est de
  2,2 × 10⁻¹⁵. Pour un modèle linéaire, ces contributions sont exactement les **valeurs SHAP**
  (variables supposées indépendantes) : aucune approximation, aucune bibliothèque ajoutée.

> [!NOTE]
> La décomposition exacte n'existe que pour un modèle linéaire. Face à un autre modèle,
> `src/explain.py` lève une erreur (`TypeError`) plutôt que de produire une explication fausse.
> Expliquer le modèle CLV (gradient boosting) ou un futur modèle non linéaire demanderait SHAP.

## La référence d'explication

Le calcul a besoin des moyennes du jeu d'entraînement, que l'API ne possède pas. Elles sont donc
calculées une fois à l'entraînement et **figées avec le modèle** dans
[`data/model_v2/explication_reference.json`](../../data/model_v2/explication_reference.json) :
moyennes des colonnes transformées, logit de référence, moyenne et médiane d'imputation de chaque
variable, modalités apprises. L'API vérifie que cette référence correspond bien aux colonnes du
modèle chargé.

## De la contribution à l'explication métier

Pour chaque compte, `src/explain.py` produit :

1. les **3 facteurs** qui augmentent le plus le risque et les **3** qui le diminuent le plus,
   formulés avec les libellés et unités de la [base de connaissance](base_de_connaissance.md),
   avec la moyenne du portefeuille pour comparer ;
2. la **trace de la décision** : score comparé au seuil D9, rang de la perte attendue parmi les
   comptes signalés, capacité D10 ;
3. des **avertissements** : valeur manquante (remplacée par la médiane), valeur hors de la plage
   du dictionnaire, modalité inconnue du modèle.

Mode d'emploi pour un CSM : [lire une explication](lire_une_explication.md).

## Au-delà du compte : contrôler et surveiller

Les mêmes contributions servent à :

- **contrôler le modèle** avant sa mise en service ([contrôles](controles.md)) ;
- **attribuer une dérive** : l'écart de logit moyen entre deux lots se décompose exactement,
  variable par variable. Sur le lot dérivé du notebook (§13.1.1), la hausse des scores s'explique à
  70 % par la récence de connexion, 18 % par le CSAT et 10,5 % par les intégrations, alors que le PSI
  de cette dernière restait sous le seuil d'alerte.

## Limites à rappeler avec chaque explication

- **Une contribution n'est pas une cause** : elle décrit ce que le modèle a appris. Ajouter une
  intégration à un compte ne réduit pas mécaniquement son risque.
- **Tout est relatif à la référence** : « augmente le risque » signifie « par rapport au compte
  moyen du jeu d'entraînement ».
- **Les variables corrélées se partagent l'effet** (licences, utilisateurs actifs, taux
  d'adoption) : le partage entre elles est instable.
- **La CLV n'est pas expliquée** : la perte attendue est expliquée pour sa probabilité, pas pour sa
  valeur.

Code : [`src/explain.py`](../../src/explain.py) · tests :
[`tests/test_explain.py`](../../tests/test_explain.py)
