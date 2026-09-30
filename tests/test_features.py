"""Tests unitaires de `src/features.py` (Gold v2) -- DataFrames synthétiques minimaux, jamais
le parquet Silver réel."""
import numpy as np
import pandas as pd

from src.features import (
    FEATURES_V2,
    LEURRES,
    REDONDANTES_CATALOGUE,
    completer_taux_adoption,
    construire_features_v2,
    masque_retards_impossibles,
    neutraliser_incoherences,
)


def _silver_minimal() -> pd.DataFrame:
    ligne = {
        "client_id": "CLI-000001", "secteur": "Tech", "taille_entreprise": "PME", "plan": "Pro",
        "pays": "France", "jour_souscription": "lundi", "code_datacenter": "eu-w1",
        "couleur_theme_interface": "clair", "groupe_experimentation": "A",
        "anciennete_mois": 12.0, "sieges_souscrits": 10.0, "utilisateurs_actifs": 8.0,
        "taux_adoption_pct": 80.0, "connexions_30j": 20.0, "heures_usage_30j": 40.0,
        "fonctionnalites_total": 10.0, "fonctionnalites_utilisees": 5.0, "nb_integrations": 2.0,
        "derniere_connexion_jours": 1.0, "tickets_support_90j": 0.0, "delai_reponse_support_h": 2.0,
        "csat": 4.0, "retards_paiement_12m": 0.0, "revenu_mensuel_recurrent_eur": 990.0,
        "prix_mensuel_par_siege_eur": 99.0, "fonctionnalites_incluses": 10.0, "sla_reponse_h": 4.0,
        "quota_stockage_go": 100.0, "support_dedie": "Non",
        "sante_compte_fin_periode": 80.0, "valeur_vie_client_eur": 1000.0, "churn": 0,
    }
    ligne_2 = dict(ligne, client_id="CLI-000002", taux_adoption_pct=np.nan, csat=np.nan)
    return pd.DataFrame([ligne, ligne_2])


class TestCompleterTauxAdoption:
    def test_valeur_manquante_recalculee_depuis_actifs_et_sieges(self):
        out = completer_taux_adoption(_silver_minimal())

        assert out["taux_adoption_pct"].tolist() == [80.0, 80.0]

    def test_sieges_nuls_laisse_la_valeur_manquante(self):
        silver = _silver_minimal()
        silver.loc[1, "sieges_souscrits"] = 0

        out = completer_taux_adoption(silver)

        assert np.isnan(out.loc[1, "taux_adoption_pct"])


class TestConstruireFeaturesV2:
    def test_colonnes_exactement_features_v2_dans_l_ordre(self):
        out = construire_features_v2(_silver_minimal())

        assert list(out.columns) == FEATURES_V2
        assert len(FEATURES_V2) == 20

    def test_aucun_leurre_ni_colonne_catalogue_ni_fuite(self):
        out = construire_features_v2(_silver_minimal())

        interdites = set(LEURRES) | set(REDONDANTES_CATALOGUE) | {
            "client_id", "sante_compte_fin_periode", "valeur_vie_client_eur", "churn",
        }
        assert interdites.isdisjoint(out.columns)

    def test_les_autres_nan_sont_laisses_au_pipeline(self):
        out = construire_features_v2(_silver_minimal())

        assert np.isnan(out.loc[1, "csat"])

    def test_ratios_v1_calcules(self):
        out = construire_features_v2(_silver_minimal())

        assert out.loc[0, "taux_utilisation_fonctionnalites"] == 0.5
        assert out.loc[0, "taux_retard_paiement_par_mois"] == 0.0


class TestNeutraliserIncoherences:
    def _silver(self, anciennete, retards):
        silver = _silver_minimal().head(1)
        return pd.concat([silver.assign(anciennete_mois=a, retards_paiement_12m=r)
                          for a, r in zip(anciennete, retards)], ignore_index=True)

    def test_plus_de_retards_que_de_mois_factures_est_impossible(self):
        silver = self._silver([1, 1, 3, 30, 30], [1, 5, 4, 12, 13])

        assert masque_retards_impossibles(silver).tolist() == [False, True, True, False, True]

    def test_valeur_impossible_neutralisee_en_nan_et_ratio_aussi(self):
        out = construire_features_v2(self._silver([1, 1], [1, 5]))

        assert out.loc[0, "retards_paiement_12m"] == 1
        assert out.loc[0, "taux_retard_paiement_par_mois"] == 1.0
        assert np.isnan(out.loc[1, "retards_paiement_12m"])
        assert np.isnan(out.loc[1, "taux_retard_paiement_par_mois"])

    def test_ratio_deja_calcule_neutralise_entree_api(self):
        X = pd.DataFrame({"anciennete_mois": [1, 12], "retards_paiement_12m": [7, 2],
                          "taux_retard_paiement_par_mois": [7.0, 2 / 12]})

        out = neutraliser_incoherences(X)

        assert out["retards_paiement_12m"].isna().tolist() == [True, False]
        assert out["taux_retard_paiement_par_mois"].isna().tolist() == [True, False]
        assert X.loc[0, "retards_paiement_12m"] == 7          # l'entrée n'est pas modifiée

    def test_valeurs_manquantes_et_colonnes_absentes_sans_effet(self):
        X = pd.DataFrame({"anciennete_mois": [np.nan, 2], "retards_paiement_12m": [3, np.nan]})

        assert not masque_retards_impossibles(X).any()
        assert not masque_retards_impossibles(X.drop(columns="anciennete_mois")).any()
