---
type: index
statut: à jour
mise_a_jour: 2026-09-29
---

# Documentation — prédiction du churn SaaS

Documentation de référence de la solution : un outil d'aide à la décision qui estime le risque de
résiliation de chaque compte client B2B, sa valeur vie client, et en déduit une liste mensuelle de
comptes à contacter en priorité, **chaque priorité étant expliquée**.

Le [notebook de certification exécuté](../reports/notebooks/notebook_certifiant_churn_saas.ipynb)
reste le livrable principal : il démontre chaque résultat. Cette documentation le résume, décrit
ce que le notebook ne montre pas (exploitation, contrat d'API, procédures) et relie chaque
affirmation à son code ou à son artefact.

## Par où commencer

| Vous êtes… | Lisez d'abord |
|---|---|
| Évaluateur ou formateur | [Besoin et solution](cadrage/besoin_et_solution.md), puis [model card churn v2](modeles/model_card_churn_v2.md) et [contrôles d'explicabilité](explicabilite/controles.md) |
| Membre de l'équipe Customer Success | [Lire l'explication d'une priorité](explicabilite/lire_une_explication.md) |
| Personne qui reprend le projet | [Guide de démarrage](exploitation/guide_de_demarrage.md), puis [architecture](exploitation/architecture.md) et [runbook](exploitation/runbook.md) |
| Intégrateur (CRM) | [Contrat de l'API](exploitation/api.md) |

## Carte de la documentation

### Cadrage
- [Besoin et solution](cadrage/besoin_et_solution.md) : contexte, trois briques, résultats clés, limites
- [Décisions D1 à D15](cadrage/decisions/index.md) : une note par décision, avec son statut
- [Hypothèses H01 à H05](cadrage/hypotheses.md)

### Données
- [Sources](donnees/sources.md) : fichiers, empreintes, accès
- [Dictionnaire de données](donnees/dictionnaire.md) : chaque colonne et son rôle dans le modèle
- [Pipeline et lignage](donnees/pipeline_et_lignage.md) : étapes DVC, manifestes, traçabilité
- [Préparation des données](donnees/preparation.md) : nettoyage, valeurs manquantes, exclusions
- [RGPD, éthique et équité](donnees/rgpd_et_ethique.md)

### Modèles
- [Model card churn v2](modeles/model_card_churn_v2.md)
- [Model card CLV v2](modeles/model_card_clv_v2.md)
- [Protocole expérimental](modeles/protocole_experimental.md)
- [Système de décision](modeles/systeme_de_decision.md)

### Explicabilité
- [Base de connaissance](explicabilite/base_de_connaissance.md)
- [Méthode d'explication](explicabilite/methode.md)
- [Contrôles d'explicabilité](explicabilite/controles.md)
- [Lire l'explication d'une priorité](explicabilite/lire_une_explication.md) (pour les CSM)

### Exploitation
- [Architecture (DAT v2)](exploitation/architecture.md)
- [Contrat de l'API](exploitation/api.md)
- [Guide de démarrage](exploitation/guide_de_demarrage.md)
- [Runbook d'exploitation](exploitation/runbook.md)
- [Supervision et mesure de l'impact](exploitation/supervision.md)

### Qualité
- [Cahier de tests](qualite/cahier_de_tests.md)
- [Intégration continue](qualite/integration_continue.md)

### Historique
- [Journal MLOps](journal/index.md) : actions menées sur le projet, pas à pas
- [Archives v1](archives/v1/dat_churn_saas_v1.md) : DAT, [guide d'expérimentation](archives/v1/guide_experimentation_churn_saas.md) et [cahier de tests](archives/v1/cahier_de_tests_churn_saas.md) de la version 1

[Glossaire](glossaire.md)

## Correspondance avec les compétences C1 à C9

| Compétence | Documentation |
|---|---|
| C1 Identifier un jeu de données pertinent | [Besoin et solution](cadrage/besoin_et_solution.md), [décisions](cadrage/decisions/index.md), [sources](donnees/sources.md) |
| C2 Risques éthiques, sociétaux & conformité | [RGPD, éthique et équité](donnees/rgpd_et_ethique.md), [D3](cadrage/decisions/D03.md), [D7](cadrage/decisions/D07.md) |
| C3 Préparer les données | [Préparation](donnees/preparation.md), [dictionnaire](donnees/dictionnaire.md), [pipeline](donnees/pipeline_et_lignage.md) |
| C4 Choisir un modèle (démarche scientifique) | [Protocole expérimental](modeles/protocole_experimental.md) |
| C5 Entraîner le modèle | [Model cards](modeles/model_card_churn_v2.md), [explicabilité](explicabilite/controles.md) |
| C6 Implémenter la solution | [Système de décision](modeles/systeme_de_decision.md), [API](exploitation/api.md), [guide de démarrage](exploitation/guide_de_demarrage.md) |
| C7 Architecture cible & contraintes | [Architecture](exploitation/architecture.md) |
| C8 Mesurer performance & impacts | [Model cards](modeles/model_card_churn_v2.md), [système de décision](modeles/systeme_de_decision.md) |
| C9 Amélioration continue | [Runbook](exploitation/runbook.md), [supervision](exploitation/supervision.md), [CI](qualite/integration_continue.md), [journal](journal/index.md) |

## Conventions de cette documentation

- **Markdown standard**, liens relatifs : elle se lit aussi bien sur GitHub que dans
  [Obsidian](https://obsidian.md) (le dépôt est un coffre Obsidian ; `.obsidian/app.json` impose
  des liens Markdown standard et exclut les dossiers de données de l'index).
- Chaque note commence par des **propriétés** : `type` (explication, référence, guide, décision,
  journal, archive), `statut` et date de mise à jour.
- Les chiffres viennent du notebook exécuté ou des artefacts du dépôt, qui font foi en cas d'écart.
  Les valeurs de la règle de décision ne sont écrites qu'à un endroit :
  [`scoring_manifest.json`](../data/model_v2/scoring_manifest.json).
- Diagrammes en Mermaid, rendus par GitHub et par Obsidian.
