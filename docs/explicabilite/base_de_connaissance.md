---
type: référence
statut: à jour
mise_a_jour: 2026-09-29
sources: knowledge/base_connaissance.yaml, src/explain.py, tests/test_explain.py
---

[← Documentation](../index.md)

# Base de connaissance

La base de connaissance écrit **ce que l'on sait du domaine avant de regarder le modèle**. Elle
se trouve dans un seul fichier versionné,
[`knowledge/base_connaissance.yaml`](../../knowledge/base_connaissance.yaml), et sert à deux
choses :

1. **formuler** les explications en langage métier : libellé, unité, valeur de référence ;
2. **contrôler** le modèle : un écart entre ce qu'il a appris et ce que l'on sait (variable exclue
   présente, effet de sens contraire, variable qui porte presque toute l'explication, valeur hors
   plage) signale une erreur possible dans les données, la préparation ou le modèle.

## Contenu

| Section | Contenu | Source |
|---|---|---|
| `variables` | Pour chacune des 20 variables du modèle : libellé, type, unité, décimales, plage, modalités, **sens attendu**, justification | Dictionnaire de l'énoncé (§2.1), EDA du notebook (§6), raisonnement métier |
| `exclusions` | 16 colonnes interdites dans le modèle, chacune avec sa catégorie et sa raison | Notebook §6 et §7 |
| `decisions` | Libellés des règles D9, D10, D14, D3 (les **valeurs** restent dans `scoring_manifest.json`) | [Décisions](../cadrage/decisions/index.md) |
| `controles` | Gravité de chaque contrôle, seuil de concentration (50 %) | Fixés a priori |

Extrait :

```yaml
variables:
  derniere_connexion_jours:
    libelle: Jours depuis la dernière connexion
    type: numerique
    unite: j
    decimales: 0
    plage: [0, 200]          # dictionnaire de l'énoncé
    sens_attendu: hausse     # une valeur plus élevée augmente le risque
    justification: Désengagement ; l'EDA montre des connexions moins récentes chez les comptes qui résilient.
    sources: [enonce, eda]
exclusions:
  sante_compte_fin_periode: {categorie: fuite, raison: "Calculée en fin de période, après la décision (AUC univariée 0,999)."}
```

## Le sens attendu

`sens_attendu` décrit l'effet attendu d'une **hausse** de la variable sur le risque de churn :

| Valeur | Signification | Contrôle de sens |
|---|---|---|
| `hausse` | Une valeur plus élevée augmente le risque | Oui |
| `baisse` | Une valeur plus élevée diminue le risque | Oui |
| `indetermine` | Aucune hypothèse défendable a priori (secteur, plan, licences, MRR…) | Non |

> [!IMPORTANT]
> **Règle d'or : le sens attendu vient du métier et de l'EDA, jamais des coefficients du modèle.**
> Recopier les coefficients rendrait le contrôle circulaire : il validerait toujours ce que le
> modèle a appris. La base a été rédigée **avant** le calcul des coefficients. Les sens d'origine
> « métier » restent des hypothèses à faire valider par l'équipe Customer Success.

## Catégories d'exclusion et gravité

| Catégorie | Colonnes | Gravité si la colonne réapparaît dans un modèle |
|---|---|---|
| Identifiant | `client_id` | bloquant |
| Cible | `churn` | bloquant |
| Fuite | `sante_compte_fin_periode` | bloquant |
| Cible secondaire | `valeur_vie_client_eur` | bloquant |
| Conformité | `commentaire_csm` | bloquant |
| Leurre | 5 colonnes | bloquant |
| Redondante | `date_souscription` et 5 colonnes du catalogue | avertissement |

« Bloquant » a un effet concret : le notebook s'arrête à ses vérifications finales (§15.3) et
l'API refuse de se déclarer prête (`/ready` en 503), donc le test de fumée de la CI échoue.

## Garanties automatiques

Les tests de [`tests/test_explain.py`](../../tests/test_explain.py) vérifient que la base reste
cohérente avec le code :

- elle décrit **exactement** les 20 variables du modèle (`FEATURES_V2` de `src/features.py`) ;
- ses exclusions couvrent les leurres, les redondances, la fuite, les cibles, l'identifiant et le
  texte libre, et aucune n'est une variable du modèle ;
- chaque catégorie d'exclusion a une gravité ; chaque fiche a un libellé, un sens valide et une
  plage (ou des modalités).

## Modifier la base

1. Modifier `knowledge/base_connaissance.yaml` dans un commit relu, en justifiant le changement
   (champ `justification`, `sources`).
2. Ne jamais aligner un sens attendu sur un coefficient observé : si le modèle contredit la base,
   c'est une anomalie à **diagnostiquer** ([contrôles](controles.md)).
3. Lancer `pytest tests/test_explain.py`, puis `dvc repro -s certification` : la base est une
   dépendance de l'étape de certification.

Voir aussi : [méthode d'explication](methode.md) · [contrôles](controles.md) ·
[dictionnaire de données](../donnees/dictionnaire.md)
