---
type: guide
statut: à jour
mise_a_jour: 2026-09-29
public: équipes Customer Success
sources: notebook §10.2.1 ; src/explain.py
---

[← Documentation](../index.md)

# Lire l'explication d'une priorité

*Guide pour les équipes Customer Success.*

Chaque compte de la liste mensuelle arrive avec une explication : **pourquoi ce score**, **pourquoi
cette priorité**, et **ce qui fragilise l'explication**. Elle sert à préparer l'échange avec le
client, et à contester une priorité qui paraît fausse. Aucune action n'est jamais déclenchée
automatiquement ([D3](../cadrage/decisions/D03.md)).

## Exemple réel

Compte du cycle simulé, dans le Top 10 par perte attendue, resté en priorité Basse (CLV estimée
973 847 €) :

```text
CLI-003591 | score 0.197 | perte attendue 192 266 € | priorité Basse
  Décision : Priorité Basse : probabilité de churn 0,197, sous le seuil de signalement D9 (0,2832).
  ▲ Revenu mensuel récurrent (MRR) : 69 461 € (moyenne 3 493,3 €), augmente le risque
  ▲ Taux d'adoption des licences : 3,7 % (moyenne 49,33 %), augmente le risque
  ▲ Licences souscrites : 817 (moyenne 72,8), augmente le risque
  ▼ Tickets support sur 90 jours : 0 (moyenne 2,5), diminue le risque
  ▼ Fonctionnalités offertes par le plan : 40 (moyenne 19,1), diminue le risque
  ▼ Délai moyen de réponse du support : 0,5 h (moyenne 12,52 h), diminue le risque
```

Premier compte en priorité Moyenne du même cycle, dont les retards de paiement impossibles ont
été neutralisés (v2.1) :

```text
CLI-001311 | score 0.544 | perte attendue 5 246 € | priorité Moyenne
  Décision : Priorité Moyenne : probabilité 0,544 ≥ seuil D9 (0,2832), mais perte attendue 5 246 €, rang 151 sur 365 comptes signalés, au-delà de la capacité de 150 comptes en priorité Haute (D10, D14).
  ▲ Ancienneté du compte : 1 mois (moyenne 10,8 mois), augmente le risque
  ▲ Intégrations tierces connectées : 0 (moyenne 2,1), augmente le risque
  ▲ Jours depuis la dernière connexion : 19 j (moyenne 7,6 j), augmente le risque
  ▼ Tickets support sur 90 jours : 1 (moyenne 2,5), diminue le risque
  ▼ Délai moyen de réponse du support : 3,5 h (moyenne 12,52 h), diminue le risque
  ▼ Retards de paiement sur 12 mois : valeur manquante, remplacée par 0, diminue le risque
  ⚠ Retards de paiement sur 12 mois : valeur manquante, remplacée par la médiane d'entraînement (0).
  ⚠ Retards de paiement par mois d'ancienneté : valeur manquante, remplacée par la médiane d'entraînement (0,00).
```

## Les quatre parties

| Partie | Ce qu'elle dit | Comment s'en servir |
|---|---|---|
| **Décision** | Quelle règle a produit la priorité : score comparé au seuil D9 ; pour un compte signalé, rang de sa perte attendue parmi les signalés et capacité de 150 | Savoir si c'est le **modèle** (score) ou la **capacité** (rang) qui décide |
| **▲ Facteurs de hausse** | Les 3 éléments du compte qui font le plus monter son risque, avec la moyenne du portefeuille | Ouvrir l'échange sur ces sujets |
| **▼ Facteurs de baisse** | Les 3 éléments qui rassurent le plus le modèle | Vérifier qu'ils sont vrais aujourd'hui |
| **⚠ Avertissements** | Valeur manquante (remplacée par la médiane), valeur hors de la plage connue, modalité inconnue | Se méfier : l'explication repose en partie sur une valeur supposée |

Dans le premier exemple, le compte vaut beaucoup mais reste en Basse : son score est sous le
seuil, sans aucun avertissement. Dans le second, deux valeurs manquantes (retards de paiement,
neutralisés car impossibles) ont été remplacées par la médiane, ce qui diminue son risque : **si le
client a en réalité des retards, son risque est sous-estimé**. C'est typiquement un compte à
vérifier avant de l'écarter. Sur le cycle simulé, 36 % des comptes ont au moins un avertissement
(hausse due aux retards neutralisés en v2.1).

## Trois cas de décision

| Décision affichée (exemples réels du cycle simulé) | Signification |
|---|---|
| « Priorité Haute : probabilité 0,834 ≥ seuil D9 (0,2832) ; perte attendue 425 421 €, rang 1 sur 365 comptes signalés, dans la capacité de 150 comptes » | Compte à risque et parmi les plus gros enjeux : appel sous 5 jours ouvrés |
| « Priorité Moyenne : probabilité 0,544 ≥ seuil D9 (0,2832), mais perte attendue 5 246 €, rang 151 sur 365 comptes signalés, au-delà de la capacité… » | Compte à risque, mais d'autres représentent une perte attendue plus forte : c'est la capacité, pas le modèle, qui le prive d'un appel |
| « Priorité Basse : probabilité sous le seuil de signalement D9 » | Le modèle ne le juge pas assez risqué pour le signaler |

## Ce qu'il ne faut pas en conclure

- **Un facteur n'est pas une cause.** « Intégrations : 5, diminue le risque » décrit ce que le
  modèle a appris sur l'ensemble des comptes ; ajouter une intégration à ce compte ne garantit pas
  de réduire son risque.
- **Tout est comparé à un compte moyen.** « Augmente le risque » veut dire « plus que pour le compte
  moyen du portefeuille ».
- **La valeur du compte n'est pas expliquée**, seule sa probabilité de départ l'est.
- **Certains départs sont invisibles dans les données** : des comptes en apparence sains partent
  quand même (budget, concurrent, renégociation). Le jugement du CSM reste indispensable.

## Obtenir l'explication

Elle est calculée par l'API de scoring avec le paramètre `?explain=true`
([contrat d'API](../exploitation/api.md)), et dans le notebook de certification (§10.2.1).

Voir aussi : [méthode d'explication](methode.md) · [système de décision](../modeles/systeme_de_decision.md)
