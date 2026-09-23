# Journal MLOps : mise sous contrôle de version, DVC, MLflow, Docker, CI

Date : 2026-09-23. Auteur des actions : Claude (assistant), à la demande de Guillaume Saidani.
But de ce journal : expliquer **ce qui a été fait, pourquoi, et comment le refaire ou le vérifier**,
pour que tu puisses le défendre devant le jury (compétences C6 et C9 surtout).

Sommaire :
0. État de départ
1. À quoi sert chaque outil
2. Actions réalisées, pas à pas (§2.1 à §2.15)
3. Ce qu'il te reste à faire (avec les commandes)
4. Livrable final : où on en est
5. Points d'attention et questions probables du jury
6. Leçons apprises : ce qu'il aurait fallu mettre en place au jour 0

---

## 0. État de départ (constaté avant toute modification)

| Sujet | Constat |
|---|---|
| Git | Aucun dépôt. Versions gérées à la main (`_v2`, `_v3`, `_old2`, `.BACKUP`) |
| GitHub | Aucun remote, aucune CI |
| DVC | Absent. Traçabilité des données par hash SHA-256 dans des manifestes JSON écrits par les notebooks (bonne pratique, mais sans stockage ni rejeu automatique) |
| MLflow | Code prêt (`src/tracking.py`, tests) mais **jamais appelé** par les notebooks ; `mlflow` et `pyyaml` absents des requirements |
| Docker | API + exporteur de dérive + Prometheus + Grafana. `drift-exporter` **unhealthy** (il héritait de la sonde de l'API, port 8000). Pipeline data et entraînement hors conteneur |
| Tests | 87 tests passants |
| Livrable | L'énoncé exige **un notebook unique** au plan imposé (§0 à §15). Il n'existe pas encore : le travail est réparti sur 7 notebooks (00 à 06) |

---

## 1. À quoi sert chaque outil (à savoir expliquer à l'oral)

| Outil | Versionne quoi | Pourquoi pas un autre |
|---|---|---|
| **Git** | Le code, les notebooks, les petits fichiers texte (manifestes, métriques) | Historique, diff et retour arrière. Pas fait pour des binaires volumineux |
| **GitHub** | Copie distante du dépôt Git, plus la CI (GitHub Actions) | Partage (lien jury) et automatisation des tests |
| **DVC** | Les données et les modèles (parquet, joblib, png), plus le **pipeline** (`dvc.yaml`) | Git ne stocke que de petits fichiers `.dvc` / `dvc.lock` (des hash) ; les binaires vont dans un stockage distant (DagsHub). `dvc repro` ne rejoue que ce qui a changé |
| **MLflow** | Les **expériences** : paramètres, métriques et artefacts de chaque entraînement | Comparer des runs dans le temps. DVC dit *quelle version* des données ; MLflow dit *ce qu'a donné chaque essai* |
| **DagsHub** | Hébergement gratuit : miroir du dépôt GitHub, stockage DVC et serveur MLflow | Un seul lien public pour les données, les modèles et les runs |
| **Docker** | L'environnement d'exécution | Le même code tourne à l'identique partout (poste, CI, serveur) |

Fil rouge de la traçabilité : **RGPD → Bronze → Silver → Gold → modèle → run MLflow**. Le lien est
fait par `gold_sha256`, présent dans `gold_manifest.json`, `model_manifest.json` **et** dans le tag
du run MLflow.

---

## 2. Actions réalisées, pas à pas

### 2.1 Sauvegarde préalable
Copie de `data/` et `notebooks/` dans le scratchpad de la session avant tout rejeu, pour pouvoir
revenir en arrière si un notebook échouait. Ce n'est pas dans le projet : c'est temporaire.

### 2.2 Git : initialisation et `.gitignore`
```bash
git init -b main
```
`.gitignore` exclut :
- **`data/rgpd/keymap_secret.json` et `keymap_client_id.parquet`** : la clé de pseudonymisation et
  la table de correspondance. Les publier annulerait la pseudonymisation (argument C2). J'ai aussi
  vérifié que le sel n'apparaît pas dans les sorties affichées du notebook 00.
- le store MLflow local (`data/model/mlflow.db`, `mlartifacts/`), les caches Python, `scratchpad/` ;
- les **supports de cours** (TP*.html, explications*.html, énoncé PDF, `exemple_pipeline_artifacts/`).
  **Choix à valider par toi** : ce ne sont pas tes livrables, et l'énoncé est un document de
  l'organisme de formation. Pour les inclure quand même, retire les lignes correspondantes.

`.gitattributes` (ajouté ensuite) : pas de conversion CRLF/LF sur les sorties du pipeline. Sans
lui, Git convertit les fins de ligne selon l'OS, les hash ne correspondent plus à `dvc.lock`, et
DVC croit que tout a changé sur la CI Linux. Vérifié par un clone de test : fichiers identiques
octet par octet.

### 2.3 MLflow branché sur les entraînements
- `src/tracking.py`, ajouts :
  - `resolve_tracking_uri()` : utilise `MLFLOW_TRACKING_URI` si la variable est définie (serveur
    DagsHub), sinon le SQLite local `data/model/mlflow.db` ;
  - `flatten_metrics()` : `metrics.json` est imbriqué et MLflow n'accepte que des scalaires, donc
    `{"foret_aleatoire": {"pr_auc_test": 0.71}}` devient `foret_aleatoire.pr_auc_test` ;
  - `log_training_run()` accepte des `tags`, des `artifacts` et un `artifact_location`.
- Notebooks **04** et **05** : nouvelle section **« §8 bis — Traçabilité MLflow »** après la
  sérialisation. Elle crée un run avec les paramètres du modèle retenu, toutes les métriques, les
  artefacts (modèle, carte modèle, manifeste, courbes) et le tag `gold_sha256`.
  `model_clv.joblib` (62 Mo) n'est volontairement pas dupliqué dans MLflow : il est déjà versionné
  par DVC.
- 4 nouveaux tests (`tests/test_tracking.py`), soit 91 tests au total, tous verts.

Voir les runs en local :
```bash
mlflow ui --backend-store-uri sqlite:///data/model/mlflow.db
# puis http://127.0.0.1:5000 : expériences churn_saas_classification et churn_saas_regression_clv
```

### 2.4 DVC : données brutes et pipeline
```bash
pip install "dvc[s3]"
dvc init
dvc add "Examen_cas d'usage candidat/churn_saas_complet.csv"   # idem échantillon et catalogue
```
`dvc add` remplace le CSV dans Git par un petit fichier `.csv.dvc` (hash MD5 + taille) ; le CSV
lui-même va dans le cache DVC, puis sur DagsHub.

`dvc.yaml` décrit **7 stages**, un par notebook : `rgpd → bronze → silver → gold → train_churn /
train_clv → scoring`. Chaque stage :
- exécute le notebook avec `jupyter nbconvert --execute` ;
- écrit la **version exécutée** dans `reports/notebooks/` (versionnée par Git : c'est la preuve
  d'exécution visible sur GitHub). Le notebook source n'est pas modifié ; sinon il changerait à
  chaque exécution alors qu'il est aussi une dépendance du stage ;
- déclare ses `deps` (entrées) et ses `outs` (sorties). Binaires : cache DVC. Manifestes, métriques
  et cartes modèle : `cache: false`, gardés dans Git car lisibles et diffables. Clés RGPD :
  `cache: false` et ignorées par Git, donc publiées nulle part.

Premier `dvc repro` complet, résultats :
- `metrics.json` **identique** à la version précédente ; `metrics_clv.json` identique à 10⁻¹⁷ près
  (bruit de calcul flottant) ;
- Silver et Gold **identiques octet par octet**. Bronze diffère, ce qui est normal : il contient la
  colonne `_ingested_at_utc`, qui change à chaque ingestion ;
- **Conclusion à retenir pour l'oral : le pipeline est reproductible** (graine 42, même hash Gold).

Commandes utiles :
```bash
dvc dag              # affiche le graphe des stages
dvc status           # qu'est-ce qui a changé depuis le dernier repro ?
dvc repro            # rejoue uniquement les stages impactés
dvc metrics show     # métriques du modèle depuis metrics.json
dvc metrics diff     # compare les métriques avec le commit précédent
```

### 2.5 Dépendances figées
- `requirements.txt` : inchangé (runtime de l'API, image légère).
- `requirements-dev.txt` : complété et figé (`nbconvert`, `ipykernel`, `matplotlib`, `optuna`,
  `mlflow`, `PyYAML`, `dvc[s3]`, `pytest`, `httpx`). Avant, il ne contenait que `pytest`, alors que
  les tests importent `mlflow`, `yaml` et `optuna`.

### 2.6 Docker
- **Correction** : `drift-exporter` a maintenant sa propre sonde (`http://localhost:9110/metrics`).
  Avant, il était marqué *unhealthy* à tort. Vérifié : les 4 services sont *healthy*.
- `Dockerfile` **multi-cible** :
  - `runtime` : l'API, comme avant ;
  - `pipeline` : environnement complet pour rejouer `dvc repro` dans un conteneur ; le projet est
    monté en volume.
- `compose.yaml` : `build.target` explicite, et service `pipeline` sous le profil `pipeline` (il ne
  démarre pas avec la stack).
- `.dockerignore` : exclut le store MLflow et `.git` de l'image.

Vérifié : dans le conteneur `pipeline`, `dvc status` répond « up to date » et 91 tests passent.
```bash
docker compose up -d                                  # stack de service
docker compose --profile pipeline run --rm pipeline   # dvc repro conteneurisé
```

### 2.7 CI GitHub Actions (`.github/workflows/ci.yml`)
À chaque push ou pull request sur `main` :
1. job `tests` : installe `requirements-dev.txt` et lance `pytest`. Aucun secret nécessaire, car
   les tests n'utilisent que des données synthétiques ;
2. job `docker` : `dvc pull` depuis DagsHub, build de l'image API, puis test de fumée sur `/health`.
   Ignoré tant que le secret `DAGSHUB_TOKEN` n'est pas configuré.

✅ **Validée le 2026-09-23** : secret `DAGSHUB_TOKEN` ajouté (GitHub → Settings → Secrets and
variables → Actions → New repository secret), run lancé à la main (Actions → CI → Run workflow).
Les jobs `tests` et `docker` sont verts. Le jeton DagsHub sert à la fois d'identifiant et de mot de
passe S3 : aucun secret « utilisateur » n'est nécessaire.
À dire au jury : chaque push vérifie automatiquement que le code passe les tests, que les données
et modèles versionnés sont récupérables depuis DagsHub, et que l'image de l'API démarre et répond.
C'est le socle d'un déploiement continu (C6, C9).

### 2.8 README et commits
- `README.md` à la racine : page d'accueil du dépôt pour le jury (résultats, structure, commandes).
  **Liens à compléter** (`<URL ... à compléter>`).
- Commits thématiques, à relire avec `git log --stat` puis `git show <id>` :
  1. import initial du projet ;
  2. tracking MLflow ;
  3. pipeline DVC ;
  4. Docker ;
  5. CI et README ;
  6. `.gitattributes` ;
  7. ce journal.

### 2.9 Push vers GitHub (2026-09-23)
```bash
git remote add origin https://github.com/guillaumesaidani-coder/churn_saas.git
git push -u origin main
```
`-u` associe la branche locale `main` à `origin/main` : ensuite, `git push` et `git pull` suffisent.
Le push a déclenché la CI (onglet **Actions**) ; le job `docker` reste ignoré tant que les secrets
DagsHub ne sont pas en place.
### 2.10 Retrait de `Livrables/` et recréation du dépôt GitHub
Tu ne voulais pas publier `Livrables/` (comptes rendus, relevés de décision, présentations), ni
`questions_jury_ml_mlops_v2.md`, que tu as déplacé dans ce dossier. Or le premier push les
contenait.
- Un simple `git rm --cached` ne suffit pas : les fichiers resteraient lisibles dans l'historique
  (n'importe quel ancien commit sur GitHub).
- Ce qui a été fait :
  1. sauvegarde complète du dépôt (`git bundle`) et du dossier ;
  2. `Livrables/` ajouté au `.gitignore` ;
  3. réécriture de l'historique **local** pour enlever ces fichiers de tous les commits :
     ```bash
     git filter-branch --prune-empty --index-filter        'git rm -r -q --cached --ignore-unmatch Livrables questions_jury_ml_mlops_v2.md' -- main
     ```
  4. tu as **supprimé le dépôt GitHub et en as recréé un**, ce qui évite de forcer un push sur un
     historique déjà publié. GitHub y avait ajouté un commit « Initial commit » (README de 2
     lignes) : il a été fusionné (`git merge --allow-unrelated-histories`) en gardant notre
     README, plutôt qu'écrasé par un push forcé ;
  5. push de l'historique propre.
- Vérification : 0 occurrence de `Livrables/` dans tous les commits de `main`. Le dossier est
  intact sur ton disque.
- Leçon à retenir : **on écrit le `.gitignore` avant le premier push**. Une fois publié, un fichier
  ne se retire proprement qu'en réécrivant l'historique.
- Certains documents publiés (`dat_churn_saas_v1.md`, `data/README.md`, `model_card.md`, fiche Gold)
  citent des fichiers de `Livrables/`. Ces références pointent vers des documents non publiés, ce qui
  est à assumer ou à reformuler.
Nom `origin` : le remote Git et le remote DVC s'appellent tous les deux `origin`, sans conflit, car
ce sont deux outils distincts.

### 2.11 Remote DVC sur DagsHub et `dvc push` (2026-09-23)
Dépôt DagsHub : https://dagshub.com/guillaume.saidani/churn_saas. Il a été créé vide, sans
connexion à GitHub : ne pas suivre les commandes `git clone` / `touch README.md` que DagsHub
affiche pour un dépôt vide, elles créeraient un second historique git.
```bash
dvc remote add origin s3://dvc                     # stockage compatible S3 de DagsHub
dvc remote modify origin endpointurl https://dagshub.com/guillaume.saidani/churn_saas.s3
dvc remote default origin
# jeton : DagsHub > avatar > Settings > Tokens (https://dagshub.com/user/settings/tokens)
dvc remote modify origin --local access_key_id <jeton>
dvc remote modify origin --local secret_access_key <jeton>
dvc push                                           # 14 fichiers envoyés
dvc status -c                                      # "Cache and remote 'origin' are in sync."
```
- `.dvc/config` (URL du remote) est **commité** ; `.dvc/config.local` (jeton) est **ignoré** par
  Git. Vérifié : le jeton n'apparaît dans aucun commit.
- Les 14 fichiers : 3 CSV bruts, 5 parquets (bronze, silver, gold, scoring), 2 modèles joblib,
  3 graphiques. Les clés RGPD ne sont pas envoyées (`cache: false`).
- **Testé** : `git clone` depuis GitHub dans un dossier vierge, puis `dvc pull` : « 14 files
  fetched », modèles et données présents. Un tiers peut donc récupérer le projet complet.
  `dvc status` n'y signale que les deux clés RGPD, qui manquent volontairement. Conséquence : chez
  un tiers, `dvc repro` rejouerait le stage `rgpd`, avec une nouvelle clé, puis tout le pipeline.
  C'est attendu : les clés ne quittent jamais ton poste.
- ⚠️ Le jeton a été collé dans la conversation avec l'assistant : **en générer un nouveau** sur
  DagsHub, supprimer l'ancien, puis relancer les deux commandes `--local`.

### 2.12 MLflow sur le serveur DagsHub (2026-09-23)
Serveur : https://dagshub.com/guillaume.saidani/churn_saas.mlflow (source : documentation DagsHub,
« MLflow tracking »).
- **Correction préalable** de `src/tracking.py` : à la création d'une expérience, le code
  imposait un dossier d'artefacts local (`file:///C:/...`). Sur un serveur distant, les artefacts
  seraient partis vers un chemin de ton PC, inaccessible pour le jury. On laisse maintenant le
  serveur choisir quand l'URI est en `http(s)`. Nouveau test associé, 92 tests au total.
- Relance du pipeline avec 3 variables d'environnement, **sans modifier les notebooks** : c'était
  le but de `resolve_tracking_uri()` (§2.3).
  ```powershell
  $env:MLFLOW_TRACKING_URI      = "https://dagshub.com/guillaume.saidani/churn_saas.mlflow"
  $env:MLFLOW_TRACKING_USERNAME = "guillaume.saidani"
  $env:MLFLOW_TRACKING_PASSWORD = "<jeton DagsHub>"   # le même que pour DVC
  python -m dvc repro
  ```
  DVC n'a rejoué que `train_churn` et `train_clv`, car leur dépendance `src/tracking.py` avait
  changé. `scoring` a été sauté : les modèles réentraînés sont **identiques octet par octet**, une
  preuve de plus de la reproductibilité.
- Vérifié côté serveur :

  | Expérience | Métriques | Paramètres | Artefacts | Tag `gold_sha256` |
  |---|---|---|---|---|
  | `churn_saas_classification` | 16 | 18 | modèle, metrics.json, model card, manifeste, 2 courbes | `c3f400321b24…` |
  | `churn_saas_regression_clv` | 13 | 22 | metrics, model card, manifeste, graphique | `c3f400321b24…` |

  Le même `gold_sha256` figure dans `gold_manifest.json` et `model_manifest.json`. On remonte ainsi
  d'un run MLflow jusqu'à la version exacte des données.
- Le store local `data/model/mlflow.db` garde les premiers runs, ceux de §2.4. Il reste utile hors
  ligne, mais **la référence à montrer au jury est le serveur DagsHub**.
- Docker : le service `pipeline` de `compose.yaml` lit déjà ces 3 variables, depuis un fichier
  `.env` (ignoré par Git).

### 2.13 Notebook unique de certification (2026-09-23)
Livrable : `notebooks/notebook_certifiant_churn_saas.ipynb` (source, sans sorties) et sa version
**exécutée** `reports/notebooks/notebook_certifiant_churn_saas.ipynb` (158 cellules, 16 figures).
Il suit le plan imposé §0 à §15 et intègre les recommandations de l'analyse critique.

**Pédagogie** : chaque cellule de code est précédée d'une cellule « 📘 Explication » (ce qu'elle
fait, pourquoi, ce qu'il faut retenir) et commentée ligne à ligne. Ces cellules portent le tag
`pedagogie`. Pour produire plus tard une version sans elles :
```bash
jupyter nbconvert --to notebook --TagRemovePreprocessor.remove_cell_tags='["pedagogie"]' \
  --output notebook_sans_pedagogie.ipynb reports/notebooks/notebook_certifiant_churn_saas.ipynb
```

**Changements dans le code (`src/`)** :
- `src/silver.py` : paramètre `impute_medians` (par défaut `True`, donc rien ne change pour la
  v1). Avec `False`, les NaN sont laissés au pipeline sklearn ;
- `src/features.py` (nouveau) : construction des 20 features du Gold v2, la même fonction servant
  à l'entraînement et au scoring d'un export brut ;
- tests : `tests/test_features.py` (6 tests) et un test de plus dans `test_silver.py`, soit
  99 tests au total, tous verts.

**Défauts de la v1 corrigés** (à savoir expliquer au jury) :

| Défaut v1 | Correction v2 |
|---|---|
| Modèle choisi sur le jeu de test | Choix en validation croisée, avec une règle fixée à l'avance |
| Seuil D9 calibré sur le test (rappel de 80 % garanti par construction) | Seuil calculé sur des prédictions hors pli du train ; le rappel mesuré sur le test (80,7 %) est honnête |
| Leurres gardés comme features | 5 leurres + 5 colonnes redondantes exclus (30 → 20 variables, même performance) |
| Médianes calculées avant le découpage train/test | Imputation dans le pipeline, ajustée sur le train ; `taux_adoption_pct` recalculé |
| Une valeur manquante faisait échouer l'API (erreur 500) | Imputation dans le pipeline, testée via l'API (code 200) |
| Modèle CLV de 62 Mo | Gradient boosting de 1,5 Mo, à performance égale |

**Ajouts** : baseline métier D8 (reformulée sans la variable de fuite), trois familles de
modèles, étude d'ablation, calibration (Brier), analyse coût/seuil, importance par permutation,
preuve que les leurres étaient inutiles dans le modèle v1, impact métier estimé avec analyse de
sensibilité, recette D15, audit d'équité avec intervalles de confiance, simulation de dérive,
test de l'API de bout en bout (`TestClient`), runs MLflow v2 publiés sur DagsHub.

**Résultats honnêtes à connaître** :
- critère D8 respecté sur le test (+0,168 de PR-AUC pour +0,15 exigé) ;
- **recette D15 partiellement non respectée** : Spearman global de 0,29 (seuil 0,7), et 16 comptes
  partis de grande valeur non signalés. Le notebook explique pourquoi (72 % de pertes réelles
  nulles ; parmi les comptes partis, Spearman = 0,85 ; 84 % de la perte réelle captée) et propose
  deux arbitrages métier, sans modifier les critères après coup ;
- dérive simulée : 2 variables sur 4 déclenchent l'alerte PSI. La dérive de la sortie du modèle
  (36 % → 75 % de comptes signalés) complète la détection.

**Pipeline** : nouvelle étape DVC `certification` (dépendances : données brutes, `src/`, Gold et
modèle v1 pour la comparaison). Les sorties Gold v2 et `data/model_v2/` (modèles, figures) sont
poussées sur DagsHub (`dvc push`, 21 fichiers). `dvc metrics show` compare les métriques v1 et v2.
Lancé avec les variables MLflow DagsHub (§2.12), le notebook publie ses runs à côté des runs v1.

**Ce qui n'est pas encore fait** :
- l'API et l'image Docker servent toujours le modèle **v1** (`data/model`). Pour passer en v2, il
  faut pointer `MODEL_DIR` vers `data/model_v2` dans `compose.yaml` et copier ce dossier dans
  l'image (`Dockerfile`) ;
- le support de présentation (`Livrables/`) n'a pas été mis à jour avec les résultats v2.

### 2.14 Code poussé aussi vers DagsHub : page de données consultable (2026-09-23)
**Problème** : le dépôt DagsHub avait été créé vide. Il recevait les données (`dvc push`) mais pas
le code. Or DagsHub lit les fichiers `.dvc` et `dvc.lock` pour savoir quels fichiers de données
afficher : sans eux, la page restait vide, alors que les données étaient bien stockées.

**Solution** : une seconde adresse de push sur le remote `origin`. **Un seul `git push` met
maintenant à jour GitHub et DagsHub.**
```bash
git remote set-url --add --push origin https://github.com/guillaumesaidani-coder/churn_saas.git
git remote set-url --add --push origin https://dagshub.com/guillaume.saidani/churn_saas.git
git push origin main
```
Résultat : `git remote -v` affiche une adresse de lecture (GitHub) et deux adresses de push (GitHub
et DagsHub).

**Piège rencontré** : le jeton personnel fonctionnait pour DVC et MLflow, mais DagsHub l'a refusé
pour git (« Authentication failed »). Pour git, DagsHub demande le **jeton par défaut** du compte
(*Default Access Token*), ou un mot de passe si le compte en a un. Tu as fait ce push toi-même
depuis ton terminal : les identifiants sont gardés par le gestionnaire d'identifiants de Windows,
et ne figurent ni dans le projet ni dans la conversation.

Visibilité : le dépôt DagsHub est **public** (Settings → Danger Zone → Change visibility :
« This repository is currently public »). **Mais DagsHub exige une connexion pour consulter tout
dépôt**, même public : c'est vérifié sur le dépôt officiel `DAGsHub-Official/dagshub-docs`, qui
redirige lui aussi vers la page de connexion. Un visiteur sans compte DagsHub ne voit donc pas
les données : il faut un lien de repli accessible sans compte (voir §3).

### 2.15 Release GitHub v2.0 : lien vers les données sans compte (2026-09-23)
DagsHub exigeant une connexion (§2.14), le lien « jeu de données » à livrer est une **release
GitHub** : https://github.com/guillaumesaidani-coder/churn_saas/releases/tag/v2.0
- Archive `churn_saas_donnees_modeles_v2.0.zip` (0,9 Mo) : 3 CSV bruts, Gold v2 (+ manifeste,
  fiche), modèles churn et CLV v2 (+ manifestes, métriques), README avec les empreintes MD5
  (identiques à DVC) et SHA-256, et un exemple de rechargement des modèles (testé).
- Préparée par l'assistant (`dist/`, ignoré par Git), publiée par toi via l'interface GitHub.
- Vérifié : release publiée, téléchargement anonyme OK, archive identique octet par octet à celle
  préparée.
- Liens ajoutés au README et à la page de garde du notebook. Seul ce texte a changé, pas le code :
  la même modification a été appliquée au notebook source et à sa version exécutée, puis
  enregistrée par `dvc commit certification`, sans réexécution (DagsHub était injoignable à ce
  moment, et une réexécution n'aurait rien changé aux résultats).

---

## 3. Ce qu'il te reste à faire (je ne peux pas le faire à ta place : ça demande tes comptes)

### 3.1 GitHub ✅ fait (§2.9, §2.10)
1. Sur github.com : **New repository**, par exemple `churn-saas-certification`, **sans** README ni
   .gitignore (le dépôt local en a déjà). Public (lien jury) ou privé avec invitation du jury.
2. Donne-moi l'URL, ou lance toi-même :
   ```bash
   git remote add origin https://github.com/<toi>/churn-saas-certification.git
   git push -u origin main
   ```

### 3.2 DagsHub (données, modèles, MLflow)
1. Crée un compte sur dagshub.com (connexion possible avec GitHub).
2. **Create → New Repository → Connect a repository → GitHub** : choisis le dépôt ci-dessus.
3. Sur la page du dépôt DagsHub, bouton **Remote** : DagsHub affiche les **commandes exactes** pour
   DVC et MLflow. Elles ressemblent à ceci (vérifie-les sur ta page, ne les recopie pas d'ici) :
   ```bash
   dvc remote add origin s3://dvc
   dvc remote modify origin endpointurl https://dagshub.com/<toi>/<depot>.s3
   dvc remote modify origin --local access_key_id <TON_TOKEN>
   dvc remote modify origin --local secret_access_key <TON_TOKEN>
   dvc remote default origin
   git add .dvc/config && git commit -m "Remote DVC DagsHub" && git push
   dvc push          # envoie les CSV, parquets et modèles
   ```
   `--local` écrit le jeton dans `.dvc/config.local`, qui n'est **jamais** commité.
   La CI suppose que le remote s'appelle `origin` : garde ce nom.
4. ✅ MLflow sur DagsHub (§2.12).
5. ✅ Secret `DAGSHUB_TOKEN` ajouté dans GitHub, CI verte (§2.7).
6. Reporte les liens GitHub, DagsHub et MLflow dans `README.md`, puis dans le notebook final.

### 3.3 Tâches de fond
- Relire `git log` et ce journal ; savoir expliquer chaque commit.
- `Livrables/` : conservé en local, non publié (§2.10).
- Les doublons manuels `_v2`, `_v3`, `_old2` n'ont plus de raison d'exister maintenant que Git garde
  l'historique. Tu peux garder la dernière version et supprimer les autres, en le faisant dans un commit.

---

## 4. Livrable final : où on en est

Exigé par l'énoncé (§3 et §5) : **un notebook unique exécuté** au plan imposé (§0 page de garde → §15
annexes), le support de présentation, le jeu de données et le modèle sérialisé. Tu dois en plus
fournir les **liens GitHub et vers le jeu de données**.

| Élément | État |
|---|---|
| Jeu de données versionné | ✅ DVC sur DagsHub (§2.11) ; **lien à livrer : release https://github.com/guillaumesaidani-coder/churn_saas/releases/tag/v2.0** (§2.15) |
| Modèles sérialisés | ✅ `model.joblib`, `model_clv.joblib` (DVC) |
| Artefacts générés | ✅ courbes, cartes modèle, manifestes ; runs MLflow en ligne sur DagsHub (§2.12) |
| Notebooks exécutés | ✅ `reports/notebooks/00` à `06`, régénérés par `dvc repro` |
| Code sur GitHub | ✅ https://github.com/guillaumesaidani-coder/churn_saas (CI verte) |
| **Notebook unique au plan imposé** | ✅ `reports/notebooks/notebook_certifiant_churn_saas.ipynb`, exécuté par `dvc repro certification` (§2.13) |
| Support de présentation | présent dans `Livrables/soutenance_churn_saas_C1_C9.pptx` (non vérifié ici), **à mettre à jour avec les résultats v2** |
| Modèle v2 servi par l'API | ⏳ l'API et Docker servent encore la v1 (§2.13) |

---

## 5. Points d'attention et questions probables du jury

- **« Pourquoi DVC et des manifestes SHA-256 ? »** Les manifestes documentent chaque étape en
  langage métier (doublons supprimés, variable de fuite, split). DVC apporte le stockage, le rejeu
  et la comparaison entre versions. Les deux sont complémentaires.
- **« Votre pipeline est-il reproductible ? »** Oui : rejeu complet le 2026-09-23, Gold identique
  octet par octet, métriques identiques.
- **Stage `rgpd`** : il génère un nouveau sel à chaque exécution, donc de nouveaux pseudonymes. Ce
  n'est pas bloquant, car la pseudonymisation n'est pas appliquée par défaut
  (`appliquee_par_defaut: false`). À dire si on te pose la question.
- **Store MLflow local** : ses chemins d'artefacts sont des chemins Windows. C'est pourquoi le
  conteneur `pipeline` utilise un store séparé (`mlruns_docker/`). Le vrai store partagé, ce sera
  DagsHub.
- **Seuil** : en v2, le seuil opérationnel D9 vaut 0,286. Il est calculé sur des prédictions hors
  pli du jeu d'entraînement et donne un rappel de 80,7 % sur le test
  (`data/model_v2/scoring_manifest.json`). Le seuil v1 (0,282) avait été calibré sur le test :
  c'est un défaut corrigé, à ne pas présenter comme une réussite.

---

## 6. Leçons apprises : ce qu'il aurait fallu mettre en place au jour 0

L'outillage MLOps de ce projet a été ajouté **en cours de route**, alors que les notebooks 00 à
06 étaient déjà écrits. Il a fonctionné, mais le retard a eu un coût concret.

### 6.1 Ce que le retard a coûté

| Problème rencontré | Cause | Ce qu'un démarrage outillé aurait évité |
|---|---|---|
| Fichiers `_v2`, `_v3`, `_old2`, `.BACKUP` | Pas de Git | Git garde l'historique ; un seul fichier suffit |
| `Livrables/` publié par erreur, dépôt GitHub supprimé et recréé, historique réécrit (§2.10) | `.gitignore` écrit juste avant le premier push | `.gitignore` et dossier privé en place avant tout fichier sensible |
| Modèle et seuil v1 choisis sur le jeu de test, sans trace de ce qui avait été comparé | Pas de suivi des expériences ni de protocole écrit | Protocole fixé avant de modéliser ; chaque essai enregistré dans MLflow |
| Runs MLflow v1 créés après coup, en rejouant les notebooks | MLflow branché à la fin | Runs enregistrés au fil de l'eau, avec la date réelle des essais |
| 87 tests, jamais lancés automatiquement | Pas de CI | Une régression détectée à chaque push |
| `requirements-dev.txt` réduit à `pytest`, alors que le code importait `mlflow` et `optuna` | Environnement non figé | Environnement complet installé et vérifié dès le départ |
| Médianes d'imputation calculées avant le découpage train/test | Découpage fait tard, dans la couche Gold | Jeu de test mis de côté au début, préparation ajustée sur le train |

**Ce qui était déjà bien pensé** : les manifestes JSON avec empreintes SHA-256 chaînées RGPD →
Bronze → Silver → Gold. C'était un versioning manuel des données, présent dès le début. DVC a
automatisé et stocké ce que le projet faisait déjà à la main.

### 6.2 Le « jour 0 » idéal, proportionné au projet

| Quand | Outils | Pourquoi à ce moment-là |
|---|---|---|
| **Jour 0, avant toute analyse** | Environnement Python figé, `git init` + `.gitignore`, dossier privé, dépôt distant, structure `data/ notebooks/ src/ tests/`, CI minimale | Tout ce qui suit est tracé ; rien de sensible ne peut partir par erreur |
| **Dès les premières données** | DVC + stockage distant, `dvc add` des données brutes | On sait toujours sur quelle version des données on travaille |
| **Dès le premier modèle** | Jeu de test mis de côté, protocole écrit, MLflow (même local), graine fixe | Chaque essai est comparable et relié à une version des données |
| **Dès qu'une étape se répète** | Fonction dans `src/` + test + étape `dvc.yaml` | Pipeline rejouable, régressions détectées |
| **Quand le modèle est stable** | API, Docker, monitoring de dérive | Inutile avant d'avoir un modèle à servir |

### 6.3 Le modèle de projet réutilisable

Pour les prochains projets, le socle « jour 0 » est prêt dans
`C:\Users\Aelion\modele_projet_mlops` (hors de ce dépôt, car c'est un outil réutilisable) :

```powershell
cd C:\Users\Aelion\modele_projet_mlops
.\init_projet.ps1 -Destination C:\Users\Aelion\mon_nouveau_projet
```

Le script copie le modèle, crée l'environnement virtuel, initialise Git et DVC, vérifie que les
tests passent, puis fait le premier commit. Le modèle contient : `.gitignore` (secrets, `.env`,
`prive/`, données, stores MLflow), `.gitattributes`, `params.yaml`, `src/` (chemins, empreintes
et manifestes, suivi MLflow local ou DagsHub), 7 tests déjà verts, une CI GitHub Actions, un
squelette de notebook (page de garde, journal de bord, vérifications finales), un `JOURNAL.md`
avec une section « protocole à écrire avant le premier modèle », et un `dvc.yaml.exemple`. Son
README reprend la checklist du jour 0 et les pièges rencontrés ici.

Testé le 2026-09-23 : génération d'un projet, 7 tests verts, premier commit ne contenant que le
socle, fichiers sensibles (`.env`, `*secret*`, données brutes, `mlflow.db`, `prive/`) bien ignorés,
notebook modèle exécuté. Le test a révélé et fait corriger deux points :
- MLflow 3 refuse désormais le stockage local en dossier `mlruns/` : le modèle utilise une base
  SQLite `mlflow.db` ;
- Windows PowerShell 5.1 lit mal les accents d'un script UTF-8 sans BOM : le script est
  enregistré avec BOM.

### 6.4 Comment le présenter au jury

Présenter ce retard honnêtement en fait un argument pour C9 (amélioration continue), appliquée
à sa propre méthode de travail : « L'outillage MLOps a été ajouté en cours de projet. J'ai
constaté concrètement ce qu'il protège : fichiers dupliqués à la main, fichier publié par erreur,
choix de modèle non tracés. J'en ai tiré un modèle de projet qui met ce socle en place au
jour 0. »
