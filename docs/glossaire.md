---
type: référence
statut: à jour
mise_a_jour: 2026-09-29
sources: notebook §15.5, complété
---

[← Documentation](index.md)

# Glossaire

| Terme | Définition |
|---|---|
| **Ablation** | Retirer ou ajouter un groupe de variables et mesurer l'effet sur la performance, pour justifier leur présence |
| **Base de connaissance** | Référentiel versionné de ce que l'on sait du domaine avant de modéliser (libellés, plages, sens attendus, exclusions) ; sert à formuler et à contrôler les explications ([détail](explicabilite/base_de_connaissance.md)) |
| **Baseline** | Référence à battre : naïve (probabilité constante) ou métier (règle simple sans apprentissage, [D8](cadrage/decisions/D08.md)) |
| **Bootstrap** | Réentraîner un modèle sur des tirages avec remise des données, pour mesurer la stabilité d'un résultat |
| **Bronze, Silver, Gold** | Couches de données : copie brute, données nettoyées, données prêtes pour le modèle |
| **Calibration / Brier** | Accord entre probabilités prédites et fréquences observées ; le score de Brier en est l'erreur quadratique |
| **Churn** | Résiliation d'un abonnement à l'échéance ([D2](cadrage/decisions/D02.md)) |
| **CLV** | Valeur vie client : revenu total attendu d'un compte sur sa durée de vie |
| **Contribution** (explication locale) | Part du score d'un compte due à une variable, mesurée par rapport à un compte de référence (moyenne du train) ; pour un modèle linéaire, égale à la valeur SHAP |
| **CSM** | Customer Success Manager : interlocuteur du client chargé de sa réussite et de sa rétention |
| **DVC** | Outil de versioning des données et des modèles, complémentaire de Git ; rejoue le pipeline (`dvc repro`) |
| **Fuite de données** | Variable contenant une information indisponible au moment de la prédiction ; elle gonfle artificiellement la performance |
| **Hors pli** (*out-of-fold*) | Prédiction faite par un modèle qui n'a pas vu la ligne à l'entraînement |
| **Importance par permutation** | Baisse de performance quand on mélange les valeurs d'une variable |
| **Leurre** | Variable sans pouvoir prédictif, ajoutée au jeu de données pour tester la démarche |
| **Logit** | Logarithme du rapport de chances `log(p / (1 − p))` ; la régression logistique est linéaire en logit |
| **Manifeste** | Fichier JSON écrit par le code à chaque étape : empreintes des entrées et sorties, paramètres, résultats |
| **MLflow** | Outil de suivi des expériences (paramètres, métriques, artefacts de chaque entraînement) |
| **Model card** | Fiche d'identité d'un modèle : usage prévu, données, performances, limites ([churn](modeles/model_card_churn_v2.md), [CLV](modeles/model_card_clv_v2.md)) |
| **Perte attendue** | Probabilité de churn × CLV estimée : l'enjeu économique d'un compte ([D14](cadrage/decisions/D14.md)) |
| **Pipeline** (modèle) | Enchaînement figé préparation + modèle, identique à l'entraînement et en production |
| **PR-AUC** | Aire sous la courbe précision-rappel ; plus informative que la ROC-AUC en classes déséquilibrées |
| **Précision** | Part des comptes signalés qui partent effectivement |
| **PSI** | Population Stability Index : mesure de dérive de la distribution d'une variable ; alerte au-delà de 0,25 |
| **Rappel** | Part des comptes qui partent effectivement détectés |
| **ROC-AUC** | Probabilité qu'un compte qui part ait un score supérieur à un compte qui reste |
| **SHAP** | Méthode d'attribution du score aux variables ; pour un modèle linéaire, elle coïncide avec les contributions exactes |
| **Validation croisée** | Découpage répété du jeu d'entraînement pour estimer la performance et sa dispersion |
