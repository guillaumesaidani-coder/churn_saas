---
type: journal
statut: historique
source: JOURNAL_MLOPS.md (découpé le 2026-09-29)
---

[← Sommaire du journal](index.md)

# 3. Ce qu'il te reste à faire (je ne peux pas le faire à ta place : ça demande tes comptes)

## 3.1 GitHub ✅ fait (§2.9, §2.10)
1. Sur github.com : **New repository**, par exemple `churn-saas-certification`, **sans** README ni
   .gitignore (le dépôt local en a déjà). Public (lien jury) ou privé avec invitation du jury.
2. Donne-moi l'URL, ou lance toi-même :
   ```bash
   git remote add origin https://github.com/<toi>/churn-saas-certification.git
   git push -u origin main
   ```

## 3.2 DagsHub (données, modèles, MLflow)
1. Crée un compte sur dagshub.com (connexion possible avec GitHub).
2. **Create → New Repository → Connect a repository → GitHub** : choisis le dépôt ci-dessus.
3. Sur la page du dépôt DagsHub, bouton **Remote** : DagsHub affiche les **commandes exactes** pour
   DVC et MLflow. Elles ressemblent à ceci (vérifie-les sur ta page, ne les recopie pas d'ici) :
   ```bash
   dvc remote add origin s3://dvc
   dvc remote modify origin endpointurl https://dagshub.com/<toi>/<depot>.s3
   dvc remote modify origin --local access_key_id <TON_TOKEN>
   dvc remote modify origin --local secret_access_key <TON_TOKEN>
   dvc remote default origin
   git add .dvc/config && git commit -m "Remote DVC DagsHub" && git push
   dvc push          # envoie les CSV, parquets et modèles
   ```
   `--local` écrit le jeton dans `.dvc/config.local`, qui n'est **jamais** commité.
   La CI suppose que le remote s'appelle `origin` : garde ce nom.
4. ✅ MLflow sur DagsHub (§2.12).
5. ✅ Secret `DAGSHUB_TOKEN` ajouté dans GitHub, CI verte (§2.7).
6. Reporte les liens GitHub, DagsHub et MLflow dans `README.md`, puis dans le notebook final.

## 3.2 bis Jeton DagsHub à renouveler ✅ fait (2026-09-23)
Le jeton enregistré dans `.dvc/config.local` et dans le secret GitHub `DAGSHUB_TOKEN` est refusé
(401). Utilise le **Default Access Token** (https://dagshub.com/user/settings/tokens), qui
fonctionne pour Git, DVC et MLflow :
```powershell
python -m dvc remote modify origin --local access_key_id <JETON_PAR_DEFAUT>
python -m dvc remote modify origin --local secret_access_key <JETON_PAR_DEFAUT>
```
puis mets à jour le secret GitHub `DAGSHUB_TOKEN` (Settings → Secrets and variables → Actions).
Sans cela, le job `docker` de la CI échoue au `dvc pull`.

## 3.3 Tâches de fond
- Relire `git log` et ce journal ; savoir expliquer chaque commit.
- `Livrables/` : conservé en local, non publié (§2.10).
- Les doublons manuels `_v2`, `_v3`, `_old2` n'ont plus de raison d'exister maintenant que Git garde
  l'historique. Tu peux garder la dernière version et supprimer les autres, en le faisant dans un commit.

---

Précédent : [2.29_lot2_reentrainement](actions/2.29_lot2_reentrainement.md) · Suivant : [04_livrable_final](04_livrable_final.md)
