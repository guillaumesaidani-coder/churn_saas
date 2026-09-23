# Model card -- Churn SaaS (classification)

**Modèle retenu :** Régression logistique
**Cible :** `churn` (résiliation à l'échéance) -- D2, atelier de cadrage n°1
**Features :** 30 (voir `data/gold/gold_manifest.json`)
**Exclusions anti-fuite :** `sante_compte_fin_periode` (D9), `commentaire_csm` (D7), `valeur_vie_client_eur`

## Performance (jeu de test, 1000 comptes, seed=42)

| Modèle | ROC-AUC | PR-AUC |
|---|---|---|
| Baseline (Dummy) | 0.534 | 0.296 |
| Régression logistique | 0.880 | 0.759 |
| Forêt aléatoire | 0.859 | 0.713 |

## Seuil de décision

**0.02** -- proposition technique basée sur un coût métier (FN = CLV
médiane des comptes churn = 6879 €, FP = hypothèse 50-150 €, non
validée), flaguant 83% des comptes test. **Statut : non figé (D5)**
-- à valider au point de contact métier n°3 avec le Head of Customer Success avant
tout usage opérationnel, en fixant à la fois le coût FP (H01) **et** une capacité
d'action mensuelle CS (non contrainte dans ce calcul).

## Usage prévu

Score d'aide à la décision pour les équipes Customer Success -- **aucune action de
rétention automatique** (D3, art. 22 RGPD). `commentaire_csm` n'est jamais utilisé
comme feature (D7).

## Limites connues

- Seuil non validé par le métier (voir ci-dessus).
- Hypothèse de coût FP non confirmée par le Head of CS (H01).
- Biais de représentation de certains segments non corrigé à ce stade (cf.
  `Livrables/architecture_donnees_churn_saas.pptx`, slide 6).
