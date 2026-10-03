---
type: référence
statut: à jour
mise_a_jour: 2026-10-03
sources: .github/workflows/ci.yml
---

[← Documentation](../index.md)

# Intégration continue

Workflow GitHub Actions [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml), déclenché à
chaque push sur `main`, à chaque pull request, et à la demande.

```mermaid
flowchart LR
    P["push / pull request"] --> T["Job tests<br/>pip install -r requirements-dev.txt<br/>ruff, pytest"]
    T -->|"réussi"| D{"Secret<br/>DAGSHUB_TOKEN ?"}
    D -- non --> S["Job docker ignoré<br/>(message d'information)"]
    D -- oui --> PULL["dvc pull<br/>données et modèles"]
    PULL --> E["Évaluation du modèle en service<br/>scripts/evaluer_modele.py"]
    E -->|"critères tenus"| B["docker build --target runtime"]
    E -->|"un critère non tenu"| X["Échec : image non construite"]
    B --> R["docker run, MODEL_DIR=data/model_v2<br/>GET /ready (30 essais, 2 s)"]
    R -->|"push sur main"| G["Publication sur ghcr.io<br/>tags : commit, latest"]
```

| Job | Étapes | Ce qu'il garantit |
|---|---|---|
| `tests` | Installation de l'environnement complet, lint `ruff check .` (règles par défaut, [`ruff.toml`](../../ruff.toml)), `python -m pytest -q` | Le code ne contient ni erreur de syntaxe, ni nom indéfini, ni import inutile ; les 215 tests passent sur Linux, Python 3.13 (le test qui lit le Gold v2 est sauté : pas de `dvc pull` dans ce job) |
| `docker` | `dvc pull` depuis DagsHub, **évaluation du modèle en service** sur le jeu de test (rapport `evaluation-modele` en artefact du run), construction de l'image d'exécution, démarrage, interrogation de `/ready` | Le modèle livré tient ses critères ([D8](../cadrage/decisions/D08.md), rappel au seuil [D9](../cadrage/decisions/D09.md), calibration, aucun contrôle bloquant) et redonne les métriques publiées dans `metrics.json` ; l'image démarre avec les **vrais** modèles v2 ; **sur un push sur `main`**, l'image testée est publiée sur GitHub Container Registry (`ghcr.io/guillaumesaidani-coder/churn_saas`), taguée par les 12 premiers caractères du commit et `latest` |

## Secret requis

`DAGSHUB_TOKEN` (Settings → Secrets and variables → Actions du dépôt GitHub). Sans lui, le job
`docker` affiche un message et s'arrête sans échec : les tests unitaires restent exécutés.

## Ce que la CI ne fait pas

- Elle ne rejoue pas le notebook de certification (trop long, et il publierait des runs MLflow) :
  c'est `dvc repro -s certification`, lancé à la main, qui le fait.
- Elle n'entraîne pas de challenger : la comparaison (`scripts/challenger.py`) se lance au
  ré-entraînement ([runbook](../exploitation/runbook.md) §3).
- Elle ne déploie pas l'image sur un serveur : la livraison s'arrête au registre, d'où l'image se
  tire et se lance ([guide de démarrage](../exploitation/guide_de_demarrage.md)). Pas de
  déploiement sur une pull request : l'image n'est publiée que depuis `main`.
- Elle suppose que les sorties DVC sont sur DagsHub : après une exécution qui modifie un modèle,
  faire `dvc push` **avant** `git push`, sinon `dvc pull` échoue dans la CI.

Voir aussi : [cahier de tests](cahier_de_tests.md) · [runbook](../exploitation/runbook.md)
