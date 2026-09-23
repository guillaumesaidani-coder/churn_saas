"""Tests unitaires de `src/gold.py` (logique de `notebooks/03_preparation_gold.ipynb` §1-§6).

Données utilisées : uniquement un DataFrame synthétique généré avec un `Generator` numpy
seedé -- jamais le parquet Silver réel -- pour isoler le piège de fuite, le calcul de
features et le split anti-fuite de la donnée métier réelle.
"""
import numpy as np
import pandas as pd
import pytest

from src.gold import (
    CATEGORICAL_CANDIDATES,
    EXCLUDED_COLUMNS_CHURN,
    EXCLUDED_COLUMNS_CLV,
    add_ratio_features,
    assign_split,
    build_gold,
    build_gold_manifest,
    cramers_v,
    identify_leurres,
    leakage_correlation_and_auc,
    select_feature_columns,
)


class TestAddRatioFeatures:
    def test_taux_utilisation_fonctionnalites(self):
        clients = pd.DataFrame({
            "fonctionnalites_utilisees": [5, 0],
            "fonctionnalites_total": [10, 0],  # 0 -> division neutralisée
            "retards_paiement_12m": [1, 2],
            "anciennete_mois": [4, 0],
        })

        out = add_ratio_features(clients)

        assert out["taux_utilisation_fonctionnalites"].tolist() == [0.5, 0.0]

    def test_taux_retard_paiement_par_mois_plancher_anciennete_a_1(self):
        clients = pd.DataFrame({
            "fonctionnalites_utilisees": [1],
            "fonctionnalites_total": [1],
            "retards_paiement_12m": [3],
            "anciennete_mois": [0],  # clip(lower=1) => diviseur = 1, pas 0
        })

        out = add_ratio_features(clients)

        assert out["taux_retard_paiement_par_mois"].tolist() == [3.0]


class TestSelectFeatureColumns:
    def test_exclut_exactement_les_colonnes_listees(self):
        columns = ["client_id", "plan", "churn", "anciennete_mois"]

        result = select_feature_columns(columns, excluded=["client_id", "churn"])

        assert result == ["plan", "anciennete_mois"]

    def test_defaut_exclut_les_colonnes_churn_documentees(self):
        columns = EXCLUDED_COLUMNS_CHURN + ["une_feature"]

        assert select_feature_columns(columns) == ["une_feature"]


class TestAssignSplit:
    def test_deterministe_a_seed_fixe(self):
        clients = pd.DataFrame({"churn": [0, 1] * 20})

        split_a = assign_split(clients, random_state=42)
        split_b = assign_split(clients, random_state=42)

        assert split_a.tolist() == split_b.tolist()

    def test_proportions_train_test_respectent_test_size(self):
        clients = pd.DataFrame({"churn": [0, 1] * 25})  # 50 lignes

        split = assign_split(clients, test_size=0.2, random_state=42)

        assert (split == "test").sum() == 10
        assert (split == "train").sum() == 40


class TestCramersV:
    def test_association_quasi_parfaite(self):
        # Correction de continuité de Yates sur une table 2x2 -> légèrement < 1, pas exactement 1.
        confusion = np.array([[50, 0], [0, 50]])

        assert cramers_v(confusion) > 0.9

    def test_independance_exacte_donne_zero(self):
        confusion = np.array([[25, 25], [25, 25]])

        assert cramers_v(confusion) == pytest.approx(0.0, abs=1e-9)


def _synthetic_clients(n: int = 200, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    churn = rng.integers(0, 2, size=n)
    # sante_compte_fin_periode fortement corrélée au churn -- piège de fuite volontaire.
    sante = np.where(churn == 1, rng.normal(0.2, 0.05, n), rng.normal(0.8, 0.05, n))

    data = {
        "client_id": [f"CLI-{i}" for i in range(n)],
        "date_souscription": pd.Timestamp("2025-01-01"),
        "commentaire_csm": "",
        "sante_compte_fin_periode": sante,
        "valeur_vie_client_eur": rng.uniform(100, 5000, n),
        "churn": churn,
    }
    for col in [
        "anciennete_mois", "sieges_souscrits", "utilisateurs_actifs", "taux_adoption_pct",
        "connexions_30j", "heures_usage_30j", "fonctionnalites_total", "fonctionnalites_utilisees",
        "nb_integrations", "derniere_connexion_jours", "tickets_support_90j",
        "delai_reponse_support_h", "csat", "retards_paiement_12m", "revenu_mensuel_recurrent_eur",
    ]:
        data[col] = rng.uniform(1, 100, n)  # sans lien construit avec churn -> candidats leurres
    for col in CATEGORICAL_CANDIDATES:
        data[col] = rng.choice(["A", "B"], size=n)

    return pd.DataFrame(data)


class TestLeakageCorrelationAndAuc:
    def test_variable_fortement_correlee_donne_une_auc_elevee(self):
        clients = _synthetic_clients()

        corr, auc = leakage_correlation_and_auc(clients)

        assert abs(corr) > 0.7
        assert auc > 0.9


class TestIdentifyLeurres:
    def test_categorielle_parfaitement_independante_est_signalee(self):
        # Construction déterministe (pas de random) : indépendance exacte entre groupe_neutre
        # et churn -- doit être détectée comme leurre quel que soit le tirage aléatoire.
        n = 100
        clients = pd.DataFrame({
            "churn": [0] * 50 + [1] * 50,
            "groupe_neutre": ["A", "B"] * 50,
        })

        leurres = identify_leurres(
            clients, numeric_candidates=[], categorical_candidates=["groupe_neutre"],
        )

        assert leurres == ["groupe_neutre"]

    def test_categorielle_fortement_associee_nest_pas_signalee(self):
        clients = pd.DataFrame({
            "churn": [0] * 50 + [1] * 50,
            "groupe_previsible": ["A"] * 50 + ["B"] * 50,
        })

        leurres = identify_leurres(
            clients, numeric_candidates=[], categorical_candidates=["groupe_previsible"],
        )

        assert leurres == []


class TestBuildGold:
    def test_structure_de_sortie_et_exclusions_anti_fuite(self):
        clients = _synthetic_clients()

        gold, info = build_gold(clients)

        assert "sante_compte_fin_periode" not in info["feature_columns"]
        assert "valeur_vie_client_eur" not in info["feature_columns"]
        assert "churn" not in info["feature_columns"]
        assert set(gold["split"].unique()) <= {"train", "test"}
        assert "sante_compte_fin_periode" not in info["feature_columns_clv"]
        assert "churn" not in info["feature_columns_clv"]

    def test_manifest_reference_bien_la_source_et_le_hash_gold(self):
        clients = _synthetic_clients()
        gold, info = build_gold(clients)

        manifest = build_gold_manifest(
            gold, info,
            sha256_source_silver="abc123",
            chemin_gold="data/gold/clients_churn_gold.parquet",
            sha256_gold="def456",
            processed_at_utc="2026-01-01T00:00:00+00:00",
        )

        assert manifest["sha256_source_silver"] == "abc123"
        assert manifest["sha256_gold"] == "def456"
        assert manifest["colonnes_exclues_du_modele"] == EXCLUDED_COLUMNS_CHURN
        assert manifest["cible_secondaire_features"]["colonnes_exclues_clv"] == EXCLUDED_COLUMNS_CLV
