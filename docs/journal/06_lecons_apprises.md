---
type: journal
statut: historique
source: JOURNAL_MLOPS.md (découpé le 2026-09-29)
---

[← Sommaire du journal](index.md)

# 6. Leçons apprises : ce qu'il aurait fallu mettre en place au jour 0

L'outillage MLOps de ce projet a été ajouté **en cours de route**, alors que les notebooks 00 à
06 étaient déjà écrits. Il a fonctionné, mais le retard a eu un coût concret.

## 6.1 Ce que le retard a coûté

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

## 6.2 Le « jour 0 » idéal, proportionné au projet

| Quand | Outils | Pourquoi à ce moment-là |
|---|---|---|
| **Jour 0, avant toute analyse** | Environnement Python figé, `git init` + `.gitignore`, dossier privé, dépôt distant, structure `data/ notebooks/ src/ tests/`, CI minimale | Tout ce qui suit est tracé ; rien de sensible ne peut partir par erreur |
| **Dès les premières données** | DVC + stockage distant, `dvc add` des données brutes | On sait toujours sur quelle version des données on travaille |
| **Dès le premier modèle** | Jeu de test mis de côté, protocole écrit, MLflow (même local), graine fixe | Chaque essai est comparable et relié à une version des données |
| **Dès qu'une étape se répète** | Fonction dans `src/` + test + étape `dvc.yaml` | Pipeline rejouable, régressions détectées |
| **Quand le modèle est stable** | API, Docker, monitoring de dérive | Inutile avant d'avoir un modèle à servir |

## 6.3 Le modèle de projet réutilisable

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

## 6.4 Comment le présenter au jury

Présenter ce retard honnêtement en fait un argument pour C9 (amélioration continue), appliquée
à sa propre méthode de travail : « L'outillage MLOps a été ajouté en cours de projet. J'ai
constaté concrètement ce qu'il protège : fichiers dupliqués à la main, fichier publié par erreur,
choix de modèle non tracés. J'en ai tiré un modèle de projet qui met ce socle en place au
jour 0. »

---

Précédent : [05_questions_jury](05_questions_jury.md)
