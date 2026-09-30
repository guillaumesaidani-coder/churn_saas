---
type: journal
statut: historique
source: JOURNAL_MLOPS.md (découpé le 2026-09-29)
---

[← Sommaire du journal](index.md)

# 1. À quoi sert chaque outil (à savoir expliquer à l'oral)

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

Précédent : [00_etat_de_depart](00_etat_de_depart.md) · Suivant : [index](actions/index.md)
