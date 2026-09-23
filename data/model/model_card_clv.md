# Model card -- Valeur vie client (régression, cible secondaire)

**Modèle retenu :** Forêt aléatoire (log-cible)
**Cible :** `valeur_vie_client_eur`, entraînée en `log(1+x)`, prédictions retransformées en euros
**Jamais utilisée comme feature du modèle de churn** (§3.2 de l'énoncé)
**Features :** 30, identiques à celles du modèle churn (voir `gold_manifest.json`)

## Performance (jeu de test, 1000 comptes, seed=42)

| Modèle | RMSE (€) | MAE (€) | R² |
|---|---|---|---|
| Baseline (médiane) | 244,135 | 81,809 | -0.102 |
| Ridge (log-cible) | 185,679 | 50,438 | 0.362 |
| Forêt aléatoire (log-cible) | 128,038 | 40,615 | 0.697 |

## Usage prévu

Enrichir la priorisation des comptes à risque (score de churn × valeur vie client
estimée) -- voir `06_implementation_scoring.ipynb`. N'est jamais consommée par le
modèle de churn.

## Limites connues

- Cible très étalée (300 € à ~2 M€) -- le RMSE reste sensible aux comptes extrêmes
  malgré le log-transform ; le MAE est la métrique de pilotage privilégiée.
- Comme le modèle churn, n'intègre aucune contrainte de capacité opérationnelle.
