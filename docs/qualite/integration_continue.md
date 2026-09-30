---
type: référence
statut: à jour
mise_a_jour: 2026-09-29
sources: .github/workflows/ci.yml
---

[← Documentation](../index.md)

# Intégration continue

Workflow GitHub Actions [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml), déclenché à
chaque push sur `main`, à chaque pull request, et à la demande.

```mermaid
flowchart LR
    P["push / pull request"] --> T["Job tests<br/>pip install -r requirements-dev.txt<br/>pytest"]
    T -->|"réussi"| D{"Secret<br/>DAGSHUB_TOKEN ?"}
    D -- non --> S["Job docker ignoré<br/>(message d'information)"]
    D -- oui --> PULL["dvc pull<br/>données et modèles"]
    PULL --> B["docker build --target runtime"]
    B --> R["docker run, MODEL_DIR=data/model_v2<br/>GET /ready (30 essais, 2 s)"]
```

| Job | Étapes | Ce qu'il garantit |
|---|---|---|
| `tests` | Installation de l'environnement complet, `python -m pytest -q` | Les 134 tests passent sur Linux, Python 3.13 |
| `docker` | `dvc pull` depuis DagsHub, construction de l'image d'exécution, démarrage, interrogation de `/ready` | L'image démarre avec les **vrais** modèles v2 ; le modèle servi ne contient aucune variable exclue par la base de connaissance (sinon `/ready` répond 503 et le job échoue) |

## Secret requis

`DAGSHUB_TOKEN` (Settings → Secrets and variables → Actions du dépôt GitHub). Sans lui, le job
`docker` affiche un message et s'arrête sans échec : les tests unitaires restent exécutés.

## Ce que la CI ne fait pas

- Elle ne rejoue pas le notebook de certification (trop long, et il publierait des runs MLflow) :
  c'est `dvc repro -s certification`, lancé à la main, qui le fait.
- Elle ne publie ni image ni modèle : pas de déploiement continu.
- Elle suppose que les sorties DVC sont sur DagsHub : après une exécution qui modifie un modèle,
  faire `dvc push` **avant** `git push`, sinon `dvc pull` échoue dans la CI.

Voir aussi : [cahier de tests](cahier_de_tests.md) · [runbook](../exploitation/runbook.md)
