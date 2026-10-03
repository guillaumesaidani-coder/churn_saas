# Fiche d'identité — Gold dataset v2

Produit par `notebooks/notebook_certifiant_churn_saas.ipynb` (commit `0ca94d1`).
Fichier : `data/gold/clients_churn_gold_v2.parquet` — SHA-256 `0dcb0bbd659c6479569accc19cde05629fe20acfbfdc43e3194d3af9abd1f865`.

## Changements par rapport à la v1
- 5 leurres exclus (jour_souscription, pays, code_datacenter, couleur_theme_interface, groupe_experimentation) : effet nul sur le churn, exclusion demandée par l'énoncé.
- 5 colonnes du catalogue exclues (prix_mensuel_par_siege_eur, fonctionnalites_incluses, sla_reponse_h, quota_stockage_go, support_dedie) : une valeur par plan.
- Imputation par la médiane déplacée dans le pipeline (ajustée sur le train) : plus de fuite train/test.
- `taux_adoption_pct` manquant recalculé (100 × actifs / sièges) au lieu d'être imputé.
- Révision v2.1 : 449 retards de paiement impossibles (plus de retards que de mois facturés) neutralisés en valeur manquante (§6.5).

## Inchangé
- Même découpage train/test que la v1 (graine 42, stratifié) : comparaison compte par compte possible.
- `sante_compte_fin_periode` conservée pour traçabilité, jamais utilisée par les modèles.

## Composition
5000 comptes, 20 features, taux de churn 28.0%.
