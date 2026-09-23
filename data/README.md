# Comment utiliser les manifestes

Chaque étape (`rgpd/`, `bronze/`, `silver/`, `gold/`, bientôt `model/`) écrit un
`*_manifest.json` en fin d'exécution de son notebook — jamais rempli à la main.
**Avant de rouvrir un notebook pour retrouver un chiffre, vérifier si le manifeste
de l'étape concernée ne l'a pas déjà.**

Depuis la v1, chaque manifeste (`rgpd_gate_manifest.json`, `bronze_manifest.json`,
`silver_manifest.json`, `gold_manifest.json`) porte un champ `version` et un ou
plusieurs champs `sha256_*` : hash du/des fichier(s) source(s) lu(s) et hash du/des
fichier(s) produit(s). Ça forme une chaîne de hash vérifiable de bout en bout
(RGPD → Bronze → Silver → Gold) : rejouer les notebooks avec les mêmes sources doit
reproduire des hash identiques ; un hash différent signale un changement réel (donnée
ou logique), pas juste une réexécution. Les manifestes modèle (`model_manifest.json`,
`model_clv_manifest.json`) référencent `gold_version` et `gold_sha256` plutôt que le
seul chemin du parquet, pour prouver quel Gold a réellement servi à l'entraînement.

Ouverture rapide dans VS Code : `Ctrl+P` → taper le nom du fichier. `Ctrl+F` dans
l'éditeur pour sauter directement à un champ. En PowerShell, pour extraire un champ
sans tout ouvrir : `(Get-Content chemin\vers\le\manifest.json | ConvertFrom-Json).nom_du_champ`.

---

## RGPD — `data/rgpd/`

Fichiers : `rgpd_gate_manifest.json`, `keymap_client_id.parquet`, `keymap_secret.json`.

**Exemple 1 — "Le client demande si des données personnelles ont été trouvées dans
les commentaires libres."**
→ `rgpd_gate_manifest.json`, champs `motifs_nominatifs_detectes` (`0`) et `decision`
(`"GO -- ingestion Bronze autorisée"`). Réponse : scan systématique sur 5035×29
valeurs, aucune correspondance.

**Exemple 2 — "Existe-t-il une version anonymisée de `client_id` utilisable pour un
export externe ?"**
→ même fichier, bloc `pseudonymisation_client_id` : `disponible: true`,
`table_correspondance` donne le chemin vers `keymap_client_id.parquet`, mais
`appliquee_par_defaut: false` — `client_id` circule tel quel tant que personne ne
décide d'utiliser la table de correspondance.

---

## Bronze — `data/bronze/`

Fichier : `bronze_manifest.json`.

**Exemple 1 — "L'échantillon de 50 lignes (`churn_saas_echantillon.csv`) a-t-il
aussi été ingéré, ou seulement le fichier complet ?"**
→ champ `tables`, 3 entrées : `clients_churn_bronze` (5035 lignes),
`catalogue_plans_bronze` (4 lignes), `clients_churn_echantillon_bronze` (50 lignes).
Les trois sont bien tracées séparément.

**Exemple 2 — "Une colonne a-t-elle été renommée ou modifiée à l'ingestion ?"**
→ champ `avertissement` ("Données brutes non corrigées...") + liste `colonnes` de
chaque table, identique au CSV source à deux ajouts près (`_source_file`,
`_ingested_at_utc`). Si une colonne manque ici, le problème vient du fichier source,
pas de l'ingestion.

---

## Silver — `data/silver/`

Fichier : `silver_manifest.json`.

**Exemple 1 — "J'ai modifié une règle de nettoyage et relancé le notebook : le
nombre de doublons supprimés a-t-il changé ?"**
→ champ `transformations` (liste de phrases, ex. `"35 doublons stricts
supprimés"`) et `lignes` (`5000`). Comparer l'ancien et le nouveau fichier — un
écart signale un changement de comportement, pas juste une exécution différente.

**Exemple 2 — "Silver dépend-il d'un serveur PostgreSQL qui pourrait manquer le
jour de la soutenance ?"**
→ champ `cible_production` : "PostgreSQL churn_saas_db.clients_churn (non
disponible dans cet environnement)". La dépendance annoncée à l'origine (TP2) est
documentée comme non active, pas cachée.

---

## Gold — `data/gold/`

Fichier : `gold_manifest.json`.

**Exemple 1 — "Pourquoi `sante_compte_fin_periode` est-elle exclue du modèle ?"**
→ bloc `piege_de_fuite` : corrélation `-0.881` avec le churn, un modèle à cette
seule variable atteint une AUC de `0.999`. Conservée dans la table pour traçabilité,
absente de `features_modele_principal`.

**Exemple 2 — "Avant de lancer un entraînement, le split est-il bien reproductible
et stratifié ?"**
→ bloc `split` : `random_state: 42`, `taux_churn_train_pct` et
`taux_churn_test_pct` tous les deux à `28.0` — même seed, même équilibre train/test
à chaque relecture du fichier, pas besoin de relancer `train_test_split` pour vérifier.

**Exemple 3 — "Quelle version du Gold a servi à entraîner le modèle, et pourquoi ces
choix (features, exclusions) ?"**
→ `gold_manifest.json`, champs `version` et `sha256_gold`, à comparer à
`gold_version`/`gold_sha256` dans `model_manifest.json` (doivent correspondre). Pour
le *pourquoi* de chaque choix (pas seulement le *quoi*), voir la fiche narrative
`data/gold/gold_fiche_identite_v1.md` — carte d'identité complète de cette version
(composition, justification des choix, hypothèses actives, valeur ajoutée attendue).
Une nouvelle version du Gold (changement de règle amont, nouvelle feature) doit créer
`gold_fiche_identite_v2.md` sans écraser la v1.

---

## Model — `data/model/`

Fichiers : `model.joblib`, `model_card.md`, `metrics.json`, `courbes_roc_pr.png`,
`cout_seuil_sensibilite.png`, `model_manifest.json`. Produits par
`04_modelisation_churn.ipynb`.

**Exemple 1 — "Quel modèle a été retenu, et pourquoi pas l'autre famille testée ?"**
→ `model_manifest.json`, champ `modele_retenu` (`"Régression logistique"`) et bloc
`metriques` : PR-AUC test 0,759 contre 0,713 pour la forêt aléatoire — critère
retenu au regard de l'énoncé (PR-AUC plus informative que l'AUC ROC en classe
déséquilibrée, 28% de churn).

**Exemple 2 — "Le seuil de décision est-il figé ?"**
→ `metrics.json`, bloc `seuil_propose` : le seuil de coût pur (0,02) est une
analyse historique de `04_modelisation_churn.ipynb`, **supersédée** par la
décision D9 du point de contact métier n°3
(`Livrables/releve_decision_pdc3_churn_saas.docx`) : seuil recalculé sur le jeu
de test pour garantir un rappel ≥ 80% -- voir `scoring_manifest.json`, bloc
`regle_decision.seuil_D9_valeur` (0,282, précision 0,627), produit par
`06_implementation_scoring.ipynb`.

**Exemple 3 — "La régression CLV réutilise-t-elle bien le principe anti-fuite ?"**
→ `model_clv_manifest.json`, produit par `05_modelisation_clv.ipynb`. Champ
`features` identique à celui du modèle churn ; `sante_compte_fin_periode` et
`churn` absentes par construction (mêmes garanties que `gold_manifest.json`, pas
une nouvelle logique).

**Exemple 4 — "Que voit un CSM concrètement, et quelle est la capacité CS
retenue (D10) ?"**
→ `scoring_manifest.json`, produit par `06_implementation_scoring.ipynb`. Bloc
`regle_decision` : seuil D9 (rappel ≥ 80%), `capacite_csm_D10` = 150 comptes/mois,
formule de priorité D14 (`perte_attendue = score_churn × valeur_vie_estimee_eur`,
sans facteur τ), et catalogue d'actions D11 (appel personnalisé / email ciblé /
surveillance passive). `scoring_exemple_cycle.parquet` montre les 5 colonnes
réellement exportées vers le CRM. Toutes ces valeurs viennent de
`Livrables/releve_decision_pdc3_churn_saas.docx` — ne pas les reproduire ailleurs
pour éviter toute divergence de numérotation ou de chiffres.
