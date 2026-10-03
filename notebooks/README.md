# Notebooks

**Le livrable est [`notebook_certifiant_churn_saas.ipynb`](notebook_certifiant_churn_saas.ipynb)**
(version 2.2). Il couvre seul le plan imposé (§0 à §15) et les compétences C1 à C9. Sa version
exécutée, avec toutes les sorties, est dans
[`reports/notebooks/`](../reports/notebooks/notebook_certifiant_churn_saas.ipynb).

Les notebooks `00` à `06` forment le **pipeline v1**, construit pendant la formation. Ils sont
conservés pour trois raisons :

- le notebook de certification s'appuie sur certaines de leurs sorties : le manifeste du portique
  RGPD, le Gold v1 (étude d'ablation, §8.4) et le modèle v1 (contrôle par la base de
  connaissance, §9.6.2) ;
- ils montrent le chemin de la v1 à la v2, raconté dans le [journal de bord](../docs/journal/index.md) ;
- leurs runs MLflow restent comparables à ceux de la v2.

| Notebook | Étape DVC | Produit | Utilisé par la certification |
|---|---|---|---|
| `00_conformite_rgpd_anonymisation` | `rgpd` | Portique RGPD : contrôle des colonnes identifiantes, pseudonymisation disponible, manifeste | **Oui** (manifeste du portique) |
| `01_ingestion_bronze` | `bronze` | Couche Bronze : lecture brute des CSV, manifeste | Indirectement (amont du Gold v1) |
| `02_nettoyage_silver` | `silver` | Couche Silver : doublons, dates, nombres en texte, catalogue | Indirectement (amont du Gold v1) |
| `03_preparation_gold` | `gold` | Gold v1 : 30 variables, découpage train/test | **Oui** (comparaison v1 / v2) |
| `04_modelisation_churn` | `train_churn` | Modèle churn v1 | **Oui** (contrôle de la base de connaissance) |
| `05_modelisation_clv` | `train_clv` | Modèle CLV v1 | Non |
| `06_implementation_scoring` | `scoring` | Règle de décision v1, exemple de cycle | Non |

La logique réutilisable a depuis été reprise dans `src/`, couverte par les tests ; les notebooks v1
en gardent leur propre copie. Ils ne sont rejoués par `dvc repro` que si leurs entrées changent.
