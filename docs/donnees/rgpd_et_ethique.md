---
type: explication
statut: à jour
mise_a_jour: 2026-09-29
sources: notebook §3.2, §4 et §12.5 ; data/rgpd/rgpd_gate_manifest.json
---

[← Documentation](../index.md)

# RGPD, éthique et équité

## Portique RGPD avant toute ingestion

Le notebook `00_conformite_rgpd_anonymisation` s'exécute **avant** l'ingestion Bronze. Il
recherche systématiquement les colonnes identifiantes et les motifs nominatifs, puis écrit sa
décision dans [`rgpd_gate_manifest.json`](../../data/rgpd/rgpd_gate_manifest.json) :

| Contrôle | Résultat |
|---|---|
| Colonnes identifiantes détectées | Aucune |
| Motifs nominatifs détectés | 0 |
| Format de `client_id` conforme (non nominatif) | Oui |
| AIPD obligatoire | Non |
| **Décision** | **GO : ingestion Bronze autorisée** |

Une **pseudonymisation** de `client_id` est disponible mais **non appliquée par défaut**
(`client_id` n'est pas nominatif). La clé et la table de correspondance ne sont **jamais
publiées** : exclues de Git et du cache DVC (voir [`.gitignore`](../../.gitignore)).

## Application des principes du RGPD

| Principe | Application dans le projet |
|---|---|
| **Base légale** (art. 6) | Intérêt légitime de l'éditeur à assurer la continuité de la relation contractuelle B2B ([D6](../cadrage/decisions/D06.md)) |
| **Finalité** (art. 5.1.b) | Priorisation des actions de rétention uniquement ; tout autre usage (évaluation d'un CSM, scoring commercial) exigerait une nouvelle analyse |
| **Minimisation** (art. 5.1.c) | Données agrégées au compte ([D1](../cadrage/decisions/D01.md)) ; texte libre exclu ([D7](../cadrage/decisions/D07.md)) ; export CRM limité à 5 colonnes |
| **Décision automatisée** (art. 22) | Score et recommandation, **jamais d'action exécutée** ([D3](../cadrage/decisions/D03.md)) : vérifié par un test automatique |
| **Registre de traitement** (art. 30) | Texte proposé (finalité, base légale, données, conservation : table de scores écrasée à chaque cycle, destinataires : équipes CS), rédigé à titre d'exercice ([H04](../cadrage/hypotheses.md)) |

Restent à faire côté client, selon le manifeste RGPD : documenter formellement base légale et
finalité, rédiger le registre, vérifier le contrat de sous-traitance en cas d'hébergement tiers
(art. 28).

## L'explication au service de l'intervention humaine

L'article 22 exige qu'un humain puisse réellement intervenir. Chaque priorité est donc livrée avec
ses raisons (facteurs de hausse et de baisse du risque, règle appliquée) et ses avertissements
(valeurs imputées, hors plage, inconnues). Un CSM peut ainsi **contester** une priorité au lieu de
la valider par principe. Voir [lire une explication](../explicabilite/lire_une_explication.md).

## Conséquences des erreurs

| Erreur | Pour le client | Pour l'éditeur |
|---|---|---|
| **Faux négatif** (compte qui part sans être signalé) | Aucune aide proposée alors qu'il rencontrait des difficultés | Perte de la CLV restante (médiane 6 879 €) |
| **Faux positif** (compte fidèle signalé) | Sollicitation non nécessaire, risque de lassitude | Temps CSM (50 à 150 €, [H01](../cadrage/hypotheses.md)) |

Le choix d'un rappel élevé ([D9](../cadrage/decisions/D09.md)) accepte davantage de faux positifs.
C'est défendable aussi du point de vue du client : l'action associée (un appel ou un email) est
**bienveillante et réversible**, pas une sanction.

## Variables écartées pour des raisons éthiques ou de conformité

- `commentaire_csm` : texte libre, risque de données personnelles ([D7](../cadrage/decisions/D07.md)).
- `pays` : sans pouvoir prédictif **et** susceptible d'introduire un traitement différencié selon
  le pays ; l'exclure supprime ce risque sans coût de performance.
- `client_id` : identifiant, sans valeur prédictive légitime.

Ces exclusions sont inscrites dans la [base de connaissance](../explicabilite/base_de_connaissance.md) :
un modèle qui les réintroduirait serait refusé automatiquement.

## Audit d'équité par segment (notebook §12.5)

Rappel et précision au seuil D9 sur le jeu de test, par segment, avec intervalle de confiance à
95 % (Wilson) :

| Segment | Modalité | Comptes | Partis | Rappel | IC 95 % | Précision |
|---|---|---|---|---|---|---|
| Taille | ETI | 197 | 41 | 0,85 | 0,72 – 0,93 | 0,73 |
| Taille | GE | 81 | 17 | 0,94 | 0,73 – 0,99 | 0,67 |
| Taille | PME | 396 | 125 | 0,77 | 0,69 – 0,83 | 0,62 |
| Taille | TPE | 326 | 97 | 0,87 | 0,78 – 0,92 | 0,61 |
| Secteur | Commerce | 162 | 50 | 0,80 | 0,67 – 0,89 | 0,63 |
| Secteur | Finance | 170 | 43 | 0,70 | 0,55 – 0,81 | 0,62 |
| Secteur | Inconnu | 54 | 15 | 0,87 | 0,62 – 0,96 | 0,65 |
| Secteur | Industrie | 150 | 42 | 0,86 | 0,72 – 0,93 | 0,65 |
| Secteur | Public | 59 | 18 | 0,83 | 0,61 – 0,94 | 0,79 |
| Secteur | Santé | 123 | 29 | 0,90 | 0,74 – 0,96 | 0,59 |
| Secteur | Tech | 168 | 51 | 0,86 | 0,74 – 0,93 | 0,63 |
| Secteur | Éducation | 114 | 32 | 0,84 | 0,68 – 0,93 | 0,57 |
| Plan | Business | 280 | 64 | 0,75 | 0,63 – 0,84 | 0,63 |
| Plan | Enterprise | 104 | 17 | 0,94 | 0,73 – 0,99 | 0,67 |
| Plan | Pro | 345 | 97 | 0,81 | 0,73 – 0,88 | 0,63 |
| Plan | Starter | 271 | 102 | 0,86 | 0,78 – 0,92 | 0,62 |


**Lecture (v2.1).** Un seul segment, **Finance** (rappel 70 %, IC 95 % de 55 % à 81 %), ne
recouvre plus le rappel global (82,5 %), de peu. Avec 16 intervalles, un tel écart est attendu par
le hasard (≈ 0,8 intervalle en moyenne) : c'est le **premier point de surveillance**. Les autres
rappels faibles (plan Business ≈ 75 %, PME ≈ 77 %) restent compatibles avec le
hasard compte tenu des effectifs. Ils sont documentés comme **points de surveillance** : si l'écart persiste sur plusieurs cycles, il faudra en
chercher la cause plutôt qu'ajuster un seuil par segment, ce qui introduirait un traitement
différencié explicite.

## Limites

- Le registre de traitement est un exercice : il devrait être validé par un DPO.
- Les effectifs par segment sont petits (15 à 125 comptes partis) : l'audit détecte les écarts
  importants, pas les écarts modérés.

Voir aussi : [décisions D1 à D15](../cadrage/decisions/index.md) · [model card churn v2](../modeles/model_card_churn_v2.md)
