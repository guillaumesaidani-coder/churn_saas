---
type: journal
statut: historique
source: JOURNAL_MLOPS.md (découpé le 2026-09-29)
---

[← Sommaire du journal](index.md)

# 4. Livrable final : où on en est

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
| Modèle v2 servi par l'API | ✅ API et Docker sur la v2 (§2.16) |
| Explicabilité et base de connaissance (demande du formateur) | ✅ notebook, API et tests (§2.20) ; **support de soutenance à compléter** avec cette partie |

---

Précédent : [03_reste_a_faire](03_reste_a_faire.md) · Suivant : [05_questions_jury](05_questions_jury.md)
