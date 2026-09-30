---
type: journal
statut: historique
source: JOURNAL_MLOPS.md (découpé le 2026-09-29)
---

[← Sommaire du journal](index.md)

# 0. État de départ (constaté avant toute modification)

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

Suivant : [01_role_des_outils](01_role_des_outils.md)
