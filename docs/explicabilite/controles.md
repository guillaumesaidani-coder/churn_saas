---
type: référence
statut: à jour
mise_a_jour: 2026-09-29
sources: src/explain.py ; notebook §9.6.1 à §9.6.3, §12.4.1 et §15.3
---

[← Documentation](../index.md)

# Contrôles d'explicabilité

Le modèle est confronté automatiquement à la [base de connaissance](base_de_connaissance.md).
Un écart ne prouve pas une erreur ; il **oblige à l'examiner**. C'est ce qui permet de « prendre
conscience qu'on a échoué quelque part ».

## Les cinq contrôles

| Contrôle | Question posée | Gravité |
|---|---|---|
| **Exclusion** | Une variable exclue (fuite, cible, identifiant, leurre…) est-elle dans le modèle ? | bloquant (redondance : avertissement) |
| **Couverture** | Chaque variable du modèle est-elle décrite dans la base ? | avertissement |
| **Sens** | Le coefficient appris va-t-il dans le sens attendu ? | avertissement |
| **Concentration** | Une seule variable porte-t-elle plus de **50 %** de l'explication ? | bloquant |
| **Modalités** | Les catégories apprises sont-elles celles du dictionnaire ? | avertissement ou information |

**Pourquoi ces gravités.** Entre variables corrélées, un coefficient peut changer de signe sans
erreur : un sens contraire n'est qu'un avertissement, qui impose une analyse. En revanche, aucune
variable disponible avant la décision ne dépasse seule une AUC de 0,76 (notebook §6) : un modèle
qui repose à plus de moitié sur une variable est suspect de fuite jusqu'à preuve du contraire.

La **part d'explication** d'une variable est la moyenne de la valeur absolue de ses contributions
sur un jeu de comptes, rapportée au total. Seuils et gravités sont fixés dans la base, a priori.

## Où les contrôles s'appliquent

| Moment | Contrôles | Effet d'un contrôle bloquant |
|---|---|---|
| Entraînement (notebook §9.6.1) | Les cinq, sur le jeu d'entraînement | Le notebook s'arrête à ses vérifications finales (§15.3) : l'étape DVC échoue |
| Démarrage de l'API | Exclusion, à partir de la liste des variables du manifeste | `/ready` répond 503 : le test de fumée de la CI échoue, l'image n'est pas validée |
| Promotion d'un nouveau modèle | Les cinq | Critère de promotion ([runbook](../exploitation/runbook.md)) |

## Résultats sur le modèle v2.1 (en service)

- **Aucun contrôle bloquant.** La variable la plus lourde (`anciennete_mois`) porte 17 % de
  l'explication, loin du maximum de 50 %.
- **12 sens attendus sur 14 respectés**, dont les 11 variables les plus influentes.
- **Deux avertissements de sens** : les deux ratios construits.

| Variable | Sens attendu | Coefficient |
|---|---|---|
| `taux_utilisation_fonctionnalites` | baisse du risque | +0,037 |
| `taux_retard_paiement_par_mois` | hausse du risque | −0,074 |

### Diagnostic des deux avertissements (notebook §9.6.3)

1. **Stabilité du signe** sur 200 réentraînements bootstrap : `taux_utilisation_fonctionnalites`
   ne garde son signe que dans 69 % des cas (instable), contre au moins 80 % pour toutes les
   autres variables numériques ; `taux_retard_paiement_par_mois` le garde dans 94 % des cas
   (contre 55 % en v2.0) : il est désormais stable.
2. **Ablation** : PR-AUC en validation croisée de 0,785 avec ces deux ratios, 0,784 sans.

Le taux d'utilisation est donc un **artefact de corrélation**. Le taux de retard est stable, mais
c'est une fonction exacte de deux variables déjà présentes (retards et ancienneté) : son
coefficient ne se lit pas comme l'effet d'un retard. Aucun des deux n'apporte rien et ils brouillent
l'explication. **Non corrigé** dans la v2.1 (la sélection a été faite avec ces variables) : retrait
recommandé pour la v3, en repassant par la procédure de sélection complète.

## Les contrôles détectent les erreurs passées du projet (notebook §9.6.2)

| Modèle testé | Résultat des contrôles |
|---|---|
| **Modèle v1** (30 variables) | 5 bloquants (les leurres), 5 avertissements (colonnes du catalogue) : n'aurait pas été mis en service |
| **Modèle avec la variable de fuite** (entraîné pour la démonstration) | PR-AUC en validation croisée de **0,997**, contre 0,785 pour le modèle retenu : aucune métrique ne l'aurait refusé. Bloqué **deux fois** : variable exclue, et **83 %** de l'explication sur cette seule variable |

Le contrôle de concentration ne dépend d'aucune liste : il aurait signalé une fuite que personne
n'avait encore identifiée.

## Expliquer les erreurs du modèle (notebook §12.4.1)

Les 14 comptes partis à forte perte et non signalés (critère [D15](../cadrage/decisions/D15.md) c)
ont été comparés aux 231 comptes partis correctement signalés :

| Variable (médiane) | 14 manqués | 231 signalés | Écart de contribution moyen |
|---|---|---|---|
| Jours depuis la dernière connexion | 1,5 | 6 | −0,80 |
| Intégrations | 1,5 | 0 | −0,54 |
| Ancienneté (mois) | 9,5 | 6 | −0,42 |
| Délai de réponse du support (h) | 7,2 | 16,2 | −0,23 |

Exception à noter (v2.1) : le compte manqué à la plus forte perte réelle, CLI-003986 (403 k€), a
1 mois d'ancienneté, aucune intégration et des retards neutralisés ; son score (0,253) est juste
sous le seuil (0,283), alors que la v2.0 le signalait.

Ces comptes ont l'air sains dans les données : **c'est une limite des données, pas du calcul**.
Aucun réglage du modèle ne les rattrapera sans nouvelles données ; cela appuie le filet de sécurité
par la valeur proposé en [D14](../cadrage/decisions/D14.md).

Voir aussi : [méthode](methode.md) · [model card churn v2](../modeles/model_card_churn_v2.md)
