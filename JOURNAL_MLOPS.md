# Journal MLOps : mise sous contrôle de version, DVC, MLflow, Docker, CI

Date : 2026-09-23. Auteur des actions : Claude (assistant), à la demande de Guillaume Saidani.
But de ce journal : expliquer **ce qui a été fait, pourquoi, et comment le refaire ou le vérifier**,
pour que tu puisses le défendre devant le jury (compétences C6 et C9 surtout).

Sommaire :
0. État de départ
1. À quoi sert chaque outil
2. Actions réalisées, pas à pas (§2.1 à §2.11)
3. Ce qu'il te reste à faire (avec les commandes)
4. Livrable final : où on en est
5. Points d'attention et questions probables du jury

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
   **Ignoré tant que les secrets `DAGSHUB_USER` / `DAGSHUB_TOKEN` ne sont pas configurés.**

⚠️ Non testée : impossible à exécuter sans le dépôt GitHub. À vérifier au premier push (onglet Actions).

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
   ⚠️ La CI suppose que le remote s'appelle `origin` : garde ce nom.
4. MLflow sur DagsHub : définis les 3 variables affichées par DagsHub (`MLFLOW_TRACKING_URI`,
   `MLFLOW_TRACKING_USERNAME`, `MLFLOW_TRACKING_PASSWORD`), puis relance l'entraînement
   (`dvc repro -f -s train_churn train_clv`). Les runs apparaissent sur DagsHub sans modifier le code.
5. GitHub → Settings → Secrets and variables → Actions : ajoute `DAGSHUB_USER` et `DAGSHUB_TOKEN`
   pour activer le job `docker` de la CI.
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
| Jeu de données versionné | ✅ DVC ; lien public dès le `dvc push` vers DagsHub (§3.2) |
| Modèles sérialisés | ✅ `model.joblib`, `model_clv.joblib` (DVC) |
| Artefacts générés | ✅ courbes, cartes modèle, manifestes, runs MLflow |
| Notebooks exécutés | ✅ `reports/notebooks/00` à `06`, régénérés par `dvc repro` |
| Code sur GitHub | ⏳ en attente de ton dépôt (§3.1) |
| **Notebook unique au plan imposé** | ❌ **à construire** : c'est le plus gros manque |
| Support de présentation | présent dans `Livrables/soutenance_churn_saas_C1_C9.pptx` (non vérifié ici) |

Pour le notebook unique, je propose : `notebooks/notebook_certifiant.ipynb` qui suit le plan §0 à
§15, **réutilise `src/`** (pas de copier-coller des notebooks 00 à 06), contient un journal de bord
par section et un §13 qui montre DVC, MLflow, la dérive et la CI. On l'ajoute au pipeline comme
stage `rapport` : `dvc repro` produit alors la version exécutée à livrer, avec les liens GitHub,
DagsHub et MLflow dans la page de garde.

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
- **Seuil** : le seuil opérationnel est celui de D9 (0,282, rappel ≥ 80 %), dans `scoring_manifest.json`.
  Le seuil de coût de `metrics.json` est une analyse historique ; `data/README.md` le précise.
