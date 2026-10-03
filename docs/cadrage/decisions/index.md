---
type: référence
statut: à jour
mise_a_jour: 2026-10-03
sources: notebook de certification §2.4 et §2.5
---

[← Documentation](../../index.md)

# Décisions de cadrage D1 à D16

Les décisions **D1 à D7** viennent de l'atelier de cadrage n°1, **D8 à D15** du point de contact métier n°3, **D16** d'un arbitrage du 2 octobre. Exercice mené seul : ce sont des choix justifiés par le candidat, pas des validations d'un commanditaire réel. Les valeurs chiffrées (seuil, capacité, actions) ne sont écrites qu'à un endroit, [`scoring_manifest.json`](../../../data/model_v2/scoring_manifest.json), que lisent le notebook et l'API.

| Décision | Objet | Statut |
|---|---|---|
| [D1](D01.md) | Unité d'analyse : le compte client B2B | appliquée |
| [D2](D02.md) | Définition du churn | appliquée |
| [D3](D03.md) | Le modèle priorise, il ne décide pas | testée automatiquement |
| [D4](D04.md) | Asymétrie des erreurs | appliquée |
| [D5](D05.md) | Seuil non fixé en atelier n°1 | close (→ D9) |
| [D6](D06.md) | Finalité unique et base légale | appliquée |
| [D7](D07.md) | Le texte libre n'est pas utilisé | contrôlée automatiquement |
| [D8](D08.md) | Critère d'acceptation du modèle | respectée |
| [D9](D09.md) | Seuil de signalement : rappel ≥ 80 % | appliquée |
| [D10](D10.md) | Capacité de l'équipe Customer Success | appliquée |
| [D11](D11.md) | Catalogue d'actions | appliquée |
| [D12](D12.md) | Mesure d'impact par groupe témoin (révisée le 2026-10-03) | outillée, sans mesure réelle |
| [D13](D13.md) | Consolidation trimestrielle de l'impact | outillée, sans bilan réel |
| [D14](D14.md) | Règle de priorité, avec filet de sécurité | appliquée |
| [D15](D15.md) | Critère de recette de la priorisation (révisé le 2026-10-03) | critères révisés, recette au premier cycle réel |
| [D16](D16.md) | Revue trimestrielle des indicateurs | décidée et outillée, aucune revue réelle |

Voir aussi : [hypothèses H01 à H07](../hypotheses.md) · [besoin et solution](../besoin_et_solution.md)
