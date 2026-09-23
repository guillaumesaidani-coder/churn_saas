---
version: v1
statut: scellée
processed_at_utc: 2026-09-21T08:58:54.865876+00:00
sha256_gold: c3f400321b243989443155f1dc62a95353eb1d2dc67e9c868f80f689bcd630a6
sha256_source_silver: 44fd8d9a1d4d09188767545cf12caade627c270009f64dbb8298bb55c3a5c0be
chemin_gold: data/gold/clients_churn_gold.parquet
manifeste_technique: data/gold/gold_manifest.json
notebook_producteur: notebooks/03_preparation_gold.ipynb
generated_by: Guillaume Saidani (Aelion)
---

# Fiche d'identité — Gold `churn_saas` — version v1

Cette fiche est la référence humaine de la version **v1** du Gold dataset. Le
manifeste technique (`gold_manifest.json`) prouve l'intégrité (hash) et permet le
rejeu ; cette fiche explique le *pourquoi* de ce qui a été scellé.

## 1. Identité et intégrité

| champ | valeur |
|---|---|
| Version | v1 (première version scellée) |
| Généré le | 2026-09-21T08:58:54 UTC |
| Hash SHA256 du parquet Gold | `c3f400321b243989443155f1dc62a95353eb1d2dc67e9c868f80f689bcd630a6` |
| Hash SHA256 de la Silver amont | `44fd8d9a1d4d09188767545cf12caade627c270009f64dbb8298bb55c3a5c0be` |
| Chaîne de rejeu | `data/rgpd` → `data/bronze` → `data/silver` → **`data/gold` (v1)** |
| Produit par | `notebooks/03_preparation_gold.ipynb`, seed=42 |
| Consommé par | `model_manifest.json` (gold_version=v1) et `model_clv_manifest.json` (gold_version=v1) — les deux modèles pointent vers le même `gold_sha256`, confirmant qu'ils ont bien été entraînés sur la même version |

Rejeu : ré-exécuter `00`→`03` avec les mêmes fichiers source doit reproduire un
parquet dont le SHA256 est identique. Un hash différent signale un changement
(donnée source modifiée, ou logique de nettoyage/préparation modifiée) et impose de
sceller une nouvelle version (v2), jamais d'écraser v1 silencieusement.

## 2. Composition — ce qui constitue cette version

- **5000 lignes, 35 colonnes** (après dédoublonnage Silver — 35 doublons stricts supprimés).
- **29 features retenues pour le modèle principal** (`features_modele_principal` du manifeste) : signaux d'usage produit (connexions, heures d'usage, adoption, intégrations), signaux support (tickets, délai, CSAT), signaux contractuels (ancienneté, plan, sièges, MRR), plus quelques colonnes de contexte/plan.
- **Pas de réduction dimensionnelle (PCA ou autre)** : les features sont utilisées brutes/encodées, aucune transformation par composantes n'est appliquée à ce stade — à mentionner explicitement si une version future en introduit une, car cela romprait l'interprétabilité par variable actuellement recherchée (permutation importance dans `model_manifest.json`).
- **Cible secondaire** : `valeur_vie_client_eur` (régression CLV), jamais utilisée comme feature du modèle churn.
- **Colonne `split`** figée (train/test stratifié, seed=42) — le split fait partie intégrante de ce qui est scellé, pas seulement les features.

## 3. Choix retenus et justification

| choix | justification |
|---|---|
| Exclusion de `sante_compte_fin_periode` du X des deux modèles | **Prouvé statistiquement**, pas un choix arbitraire : corrélation -0.881 avec `churn`, AUC univarié 0.999 (`piege_de_fuite` du manifeste) — variable calculée en fin de période, indisponible au moment du scoring réel |
| Exclusion de `commentaire_csm` | D07 (atelier n°1, cf. `Livrables/gold_dataset_atelier_cadrage_churn_saas.md`) — champ texte libre à risque résiduel de contenu nominatif |
| Exclusion de `client_id`, `date_souscription`, `valeur_vie_client_eur`, `churn` du X | identifiant et cible, exclusion structurelle standard |
| 6 "leurres" identifiés (`leurres_identifies`) conservés dans les colonnes mais signalés | variables à AUC univarié faible/suspect ou sans pouvoir prédictif réel (ex. `couleur_theme_interface`, `code_datacenter`) — gardées pour test de robustesse du modèle (le rang moyen des leurres en importance doit rester bas), pas comme features utiles |
| Split stratifié, seed=42, 80/20 | reproductibilité du split lui-même : figé une fois pour toutes en Gold plutôt que relancé à chaque notebook de modélisation, pour que tous les modèles (churn, CLV) soient comparables sur les mêmes lignes de test |

## 4. Hypothèses actives à cette version (non validées, à surveiller)

Héritées de `Livrables/gold_dataset_atelier_cadrage_churn_saas.md` (§4, `assumption`) — elles ne sont pas propres au parquet Gold, mais conditionnent l'usage qui en est fait :

- **H03** — `sante_compte_fin_periode` est supposée calculée après la fin de la période observée ; c'est ce qui justifie son exclusion. Traité comme suffisamment démontré par la preuve statistique elle-même, faute de propriétaire de la donnée à consulter dans cet exercice.
- Si un vrai propriétaire de la donnée infirmait H03 dans une itération future, cela remettrait en cause le choix d'exclusion ci-dessus et déclencherait une v2.

## 5. Valeur ajoutée attendue de cette version

- **Anti-fuite** : en excluant la variable qui produit une séparation quasi parfaite (AUC 0.999), le modèle entraîné sur ce Gold donne une mesure de performance réaliste et généralisable, au prix d'une AUC volontairement plus basse (0.88 en régression logistique, cf. `model_manifest.json`) — c'est un résultat *attendu et recherché*, pas une dégradation à corriger.
- **Reproductibilité** : deux modèles (churn, CLV) entraînés séparément sur cette version produisent des manifestes qui référencent le même `gold_sha256` — la chaîne de traçabilité version→modèle est vérifiée en pratique, pas seulement en principe.
- **Comparabilité future** : toute v2 (ex. nouvelle règle de nettoyage Silver, nouvelle feature) pourra être comparée à v1 à métriques égales grâce au split figé et documenté.

## 6. Statut

**Scellée.** Ne pas modifier `clients_churn_gold.parquet` ni `gold_manifest.json` en
place pour cette version : toute évolution (nouvelle règle de nettoyage amont,
nouvelle feature, nouvelle exclusion) doit produire une **v2** avec son propre hash
et sa propre fiche, en conservant v1 intacte pour permettre la comparaison et le
retour en arrière.
