---
type: référence
statut: à jour
mise_a_jour: 2026-09-29
sources: document de cadrage de l'atelier n°1 (non publié) pour H01 à H04 ; notebook §12.3 pour H05
---

[← Documentation](../index.md)

# Hypothèses H01 à H05

Une hypothèse est un paramètre de raisonnement **non vérifiable dans les données** de cet
exercice, faute de commanditaire réel. Elle est étiquetée comme telle partout où elle sert, et
testée en sensibilité quand elle influence un chiffre. Aucune hypothèse ne doit être présentée
comme un fait mesuré.

| # | Hypothèse | Où elle sert | Limite assumée |
|---|---|---|---|
| H01 | Coût d'une relance CS : **50 à 150 €** (30 à 60 min de temps CSM chargé) | Motive l'asymétrie [D4](decisions/D04.md) ; bornes de l'analyse de coût (§9.5) et de l'estimation d'impact (§12.3) | Ne fixe **pas** le seuil final : [D9](decisions/D09.md) le fixe par une cible de rappel |
| H02 | Rapport de coût faux négatif / faux positif dérivé de F14 et H01 | Justifie de privilégier le rappel ([D4](decisions/D04.md)) | Hérite de l'incertitude de H01. Valeur à harmoniser : voir l'avertissement de [D4](decisions/D04.md) |
| H03 | `sante_compte_fin_periode` est calculée **après** la fin de la période observée | Exclusion de la variable comme fuite de données | Aucun propriétaire de la donnée pour le confirmer ; la preuve est statistique (AUC univariée de 0,999, §6) |
| H04 | Texte du registre de traitement (finalité, base légale, conservation, destinataires) | Conformité RGPD, compétence C2 | Rédigé à titre d'exercice : à faire valider par un DPO dans un contexte réel |
| H05 | Taux de succès des relances : **10, 20 ou 30 %** | Traduction de la liste en comptes sauvés et en gain net (§12.3) | Inconnu : seule la mesure par groupe témoin ([D12](decisions/D12.md)) le remplacera par une valeur observée |

## Fait associé

**F14** — valeur vie client médiane des comptes qui résilient : **6 879 €**. C'est une mesure sur
les données, pas une hypothèse ; elle sert de coût d'un faux négatif dans l'analyse de coût
(§9.5).

## Robustesse

- **H01, H02** : les deux bornes de H01 mènent à la même conclusion qualitative (favoriser le
  rappel), ce qui rend D9 robuste à leur incertitude.
- **H05** : même avec l'hypothèse la plus prudente (10 %) et le coût de relance le plus élevé
  (150 €), le gain net estimé de la liste reste positif (§12.3).

Voir aussi : [décisions D1 à D15](decisions/index.md) ·
[notebook de certification](../../reports/notebooks/notebook_certifiant_churn_saas.ipynb), §9.5 et §12.3
