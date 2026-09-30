---
type: journal
statut: historique
source: JOURNAL_MLOPS.md (découpé le 2026-09-29)
---

[← Sommaire du journal](index.md)

# 5. Points d'attention et questions probables du jury

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
- **Seuil** : en v2 (v2.1), le seuil opérationnel D9 vaut 0,283. Il est calculé sur des prédictions hors
  pli du jeu d'entraînement et donne un rappel de 82,5 % sur le test
  (`data/model_v2/scoring_manifest.json`). Le seuil v1 (0,282) avait été calibré sur le test :
  c'est un défaut corrigé, à ne pas présenter comme une réussite.
- **« Pourquoi pas SHAP ou LIME ? »** Pour une régression logistique, les contributions
  coefficient × écart à la moyenne sont exactement les valeurs SHAP ; LIME n'apporterait qu'une
  approximation d'un modèle déjà lisible. SHAP deviendra nécessaire si le modèle retenu n'est plus
  linéaire (et dès maintenant pour expliquer la CLV).
- **« Votre base de connaissance n'est-elle pas circulaire ? »** Non : les sens attendus viennent
  du métier et de l'EDA (effets pris un par un), pas des coefficients, et la base l'interdit
  explicitement. Preuve qu'elle n'est pas complaisante : elle a levé deux avertissements sur le
  modèle retenu.
- **« Une contribution est-elle une cause ? »** Non : elle décrit ce que le modèle a appris ;
  ajouter une intégration à un compte ne réduit pas mécaniquement son risque.
- **« Que se passe-t-il si un futur modèle contient une fuite ? »** Le notebook s'arrête (§15.3),
  `/ready` répond 503 et le test de fumée de la CI échoue : le modèle ne peut pas être servi.

---

Précédent : [04_livrable_final](04_livrable_final.md) · Suivant : [06_lecons_apprises](06_lecons_apprises.md)
