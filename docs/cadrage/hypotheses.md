---
type: référence
statut: à jour
mise_a_jour: 2026-10-03
sources: document de cadrage de l'atelier n°1 (non publié) pour H01 à H04 ; notebook §12.3 pour H05 ; énoncé du cas d'usage et réponse du formateur (2026-10-03) pour H06
---

[← Documentation](../index.md)

# Hypothèses H01 à H06

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
| H05 | Taux de succès des relances : **10, 20 ou 30 %** | Traduction de la liste en comptes sauvés et en gain net (§12.3) | Inconnu : seule la mesure par groupe témoin ([D12](decisions/D12.md)) le remplacera par une valeur observée (effet de l'email et gain de l'appel sur l'email) |
| H06 | Échéance contractuelle **mensuelle** : un compte scoré au cycle M arrive à échéance avant le cycle M+1 ; `churn = 1` s'il résilie à cette échéance. Horizon de la cible : **1 mois** | Durée de conservation des scores par compte ([journal des scores](../exploitation/runbook.md)) ; protocole du groupe témoin ([D12](decisions/D12.md)) ; délai avant de connaître le rappel réel d'un cycle | L'énoncé dit « chaque mois, les clients paient » (p. 1) et « résiliation à l'échéance » (p. 2) sans préciser la durée entre deux échéances : payer chaque mois n'implique pas un contrat mensuel. **Confirmée par le formateur le 2026-10-03** (voir indice ci-dessous) |

## Fait associé

**F14** — valeur vie client médiane des comptes qui résilient : **6 879 €**. C'est une mesure sur
les données, pas une hypothèse ; elle sert de coût d'un faux négatif dans l'analyse de coût
(§9.5).

## Indice dans les données pour H06

Taux de churn selon l'ancienneté (table Silver, 5 000 comptes) :

| Ancienneté (mois) | 1 | 6 | 11 | **12** | 13 | 23 | **24** | 25 |
|---|---|---|---|---|---|---|---|---|
| Taux de churn | 54 % | 39 % | 26 % | **20 %** | 21 % | 9 % | **11 %** | 3 % |

Le churn baisse régulièrement avec l'ancienneté, sans pic aux dates anniversaires (12, 24 ou
36 mois ; à 36 mois, un seul compte, non interprétable). Avec des contrats annuels, on s'attendrait à voir les résiliations se concentrer à ces
dates. Les données vont donc plutôt dans le sens d'une échéance mensuelle, mais ce n'est pas une
preuve : le jeu est synthétique et a pu être généré sans modéliser les contrats ; aucun test
statistique n'a été fait. C'est la confirmation du formateur qui fonde H06.

## Robustesse

- **H01, H02** : les deux bornes de H01 mènent à la même conclusion qualitative (favoriser le
  rappel), ce qui rend D9 robuste à leur incertitude.
- **H05** : même avec l'hypothèse la plus prudente (10 %) et le coût de relance le plus élevé
  (150 €), le gain net estimé de la liste reste positif (§12.3).
- **H06** : avec une échéance annuelle, l'horizon de la cible pourrait atteindre 12 mois ; la
  conservation des scores par compte et le protocole du groupe témoin seraient à revoir.

Voir aussi : [décisions D1 à D15](decisions/index.md) ·
[notebook de certification](../../reports/notebooks/notebook_certifiant_churn_saas.ipynb), §9.5 et §12.3
