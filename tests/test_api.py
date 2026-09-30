"""Tests unitaires de `src/api.py` -- portage des contrôles de service (auth, limite de
débit, taille de payload, id de requête, /health, /ready, /metrics) de
`py-init/ml/src/indusense/api/main.py` vers le scoring churn+CLV.

Artefacts utilisés : jamais `data/model/` réel -- des modèles factices picklables (joblib) et
des manifestes minimaux écrits dans `tmp_path`, chargés via `load_artifacts(tmp_path)` pour
isoler le comportement de l'API du contenu réel des modèles.
"""
import json

import joblib
import numpy as np
import pytest
from fastapi.testclient import TestClient

import src.api as api_module
from src.api import app, load_artifacts

API_KEY = "dev-local-key"


class FakeModelChurn:
    """Score de churn déterministe : proportionnel à `signal`, pour calculer l'attendu à la main."""

    def predict_proba(self, X):
        proba = np.clip(X["signal"].to_numpy(dtype=float), 0, 1)
        return np.column_stack([1 - proba, proba])


class FakeModelCLV:
    def predict(self, X):
        return np.log1p(X["signal"].to_numpy(dtype=float) * 1000)


@pytest.fixture
def artifacts_dir(tmp_path):
    joblib.dump(FakeModelChurn(), tmp_path / "model.joblib")
    joblib.dump(FakeModelCLV(), tmp_path / "model_clv.joblib")

    (tmp_path / "model_manifest.json").write_text(
        json.dumps({"features": ["signal"]}), encoding="utf-8",
    )
    (tmp_path / "scoring_manifest.json").write_text(
        json.dumps({"regle_decision": {"seuil_D9_valeur": 0.5, "capacite_csm_D10": 1}}),
        encoding="utf-8",
    )
    load_artifacts(tmp_path)
    yield tmp_path


@pytest.fixture
def client(artifacts_dir):
    return TestClient(app)


def _headers():
    return {"X-API-Key": API_KEY}


class TestHealthAndReady:
    def test_health_ne_necessite_aucune_authentification(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_ready_ok_quand_les_artefacts_sont_charges(self, client):
        response = client.get("/ready")
        assert response.status_code == 200

    def test_ready_503_quand_aucun_artefact_charge(self, tmp_path, client):
        # `client` a déjà chargé des artefacts valides (fixture `artifacts_dir`) -- on pointe
        # ici vers un répertoire distinct et vide pour vérifier le comportement à froid.
        load_artifacts(tmp_path / "vide")
        response = client.get("/ready")
        assert response.status_code == 503


class TestScoreBatchAuth:
    def test_sans_cle_api_401(self, client):
        response = client.post("/score-batch", json={"clients": []})
        assert response.status_code == 401

    def test_mauvaise_cle_api_401(self, client):
        response = client.post("/score-batch", json={"clients": []}, headers={"X-API-Key": "mauvaise"})
        assert response.status_code == 401

    def test_liste_vide_422(self, client):
        response = client.post("/score-batch", json={"clients": []}, headers=_headers())
        assert response.status_code == 422


class TestScoreBatchCalcul:
    def test_scoring_et_priorite_bout_en_bout(self, client):
        payload = {
            "clients": [
                {"client_id": "CLI-1", "features": {"signal": 0.9}},  # au-dessus du seuil (0.5), perte forte
                {"client_id": "CLI-2", "features": {"signal": 0.1}},  # sous le seuil
            ]
        }

        response = client.post("/score-batch", json=payload, headers=_headers())

        assert response.status_code == 200
        resultats = {r["client_id"]: r for r in response.json()["resultats"]}
        assert resultats["CLI-1"]["score_churn"] == 0.9
        assert resultats["CLI-1"]["priorite"] == "Haute"  # capacité D10=1, seul signalé
        assert resultats["CLI-2"]["priorite"] == "Basse"  # sous le seuil D9

    def test_retards_impossibles_neutralises_avant_le_modele(self, client, monkeypatch):
        """Même règle qu'à l'entraînement (src/features.py) : 5 retards pour 1 mois -> NaN."""
        vus = []

        class ModeleEnregistreur(FakeModelChurn):
            def predict_proba(self, X):
                vus.append(X.copy())
                return super().predict_proba(X)

        monkeypatch.setattr(api_module, "_model_churn", ModeleEnregistreur())
        monkeypatch.setattr(api_module, "_feature_columns", ["signal", "anciennete_mois", "retards_paiement_12m"])
        payload = {"clients": [
            {"client_id": "CLI-1", "features": {"signal": 0.9, "anciennete_mois": 1, "retards_paiement_12m": 5}},
            {"client_id": "CLI-2", "features": {"signal": 0.1, "anciennete_mois": 24, "retards_paiement_12m": 2}},
        ]}

        response = client.post("/score-batch", json=payload, headers=_headers())

        assert response.status_code == 200
        assert vus[0]["retards_paiement_12m"].isna().tolist() == [True, False]

    def test_reponse_porte_un_request_id(self, client):
        response = client.get("/health")
        assert "X-Request-ID" in response.headers


class TestLimiteTaillePayload:
    def test_payload_trop_gros_413(self, client, monkeypatch):
        monkeypatch.setattr(api_module, "MAX_BODY_BYTES", 50)
        gros_payload = {"clients": [{"client_id": "CLI-1", "features": {"signal": 0.5, "bruit": "x" * 500}}]}

        response = client.post("/score-batch", json=gros_payload, headers=_headers())

        assert response.status_code == 413


class TestLimiteDeDebit:
    def test_429_au_dela_de_la_limite(self, client, monkeypatch):
        monkeypatch.setattr(api_module, "RATE_LIMIT_PER_MINUTE", 2)
        api_module._rate_limit_state.clear()
        payload = {"clients": [{"client_id": "CLI-1", "features": {"signal": 0.1}}]}

        for _ in range(2):
            response = client.post("/score-batch", json=payload, headers=_headers())
            assert response.status_code == 200

        response = client.post("/score-batch", json=payload, headers=_headers())
        assert response.status_code == 429


class TestMetrics:
    def test_metrics_expose_les_compteurs_prometheus(self, client):
        client.get("/health")
        response = client.get("/metrics")
        assert response.status_code == 200
        assert b"churn_saas_http_requests_total" in response.content


class FakeModelCLVConstante:
    def predict(self, X):
        return np.full(len(X), np.log1p(1000.0))


@pytest.fixture
def client_explicable(tmp_path):
    """Vrai pipeline linéaire (même structure que le modèle du projet) + sa référence
    d'explication ; la base de connaissance est celle du projet (variables `plan` et
    `derniere_connexion_jours`)."""
    import pandas as pd
    from sklearn.compose import ColumnTransformer
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    from src.explain import NOM_FICHIER_REFERENCE, reference_explication

    rng = np.random.default_rng(0)
    X = pd.DataFrame({"plan": rng.choice(["Starter", "Pro"], 300),
                      "derniere_connexion_jours": rng.integers(0, 120, 300).astype(float)})
    y = (X["derniere_connexion_jours"] + rng.normal(0, 20, 300) > 60).astype(int)
    modele = Pipeline([
        ("preparation", ColumnTransformer([
            ("cat", OneHotEncoder(handle_unknown="ignore"), ["plan"]),
            ("num", Pipeline([("imputation", SimpleImputer(strategy="median")),
                              ("standardisation", StandardScaler())]), ["derniere_connexion_jours"]),
        ])),
        ("modele", LogisticRegression()),
    ]).fit(X, y)

    joblib.dump(modele, tmp_path / "model.joblib")
    joblib.dump(FakeModelCLVConstante(), tmp_path / "model_clv.joblib")
    (tmp_path / "model_manifest.json").write_text(json.dumps({"features": list(X.columns)}), encoding="utf-8")
    (tmp_path / "scoring_manifest.json").write_text(
        json.dumps({"regle_decision": {"seuil_D9_valeur": 0.5, "capacite_csm_D10": 1}}), encoding="utf-8")
    (tmp_path / NOM_FICHIER_REFERENCE).write_text(json.dumps(reference_explication(modele, X)), encoding="utf-8")
    load_artifacts(tmp_path)
    api_module._rate_limit_state.clear()
    return TestClient(app)


class TestExplications:
    def test_sans_explain_la_reponse_est_inchangee(self, client):
        payload = {"clients": [{"client_id": "CLI-1", "features": {"signal": 0.9}}]}
        resultat = client.post("/score-batch", json=payload, headers=_headers()).json()["resultats"][0]
        assert "explication" not in resultat

    def test_explain_sans_reference_503(self, client):
        payload = {"clients": [{"client_id": "CLI-1", "features": {"signal": 0.9}}]}
        response = client.post("/score-batch?explain=true", json=payload, headers=_headers())
        assert response.status_code == 503

    def test_explain_facteurs_decision_avertissements(self, client_explicable):
        payload = {"clients": [
            {"client_id": "CLI-1", "features": {"plan": "Starter", "derniere_connexion_jours": 115}},
            {"client_id": "CLI-2", "features": {"plan": "Premium", "derniere_connexion_jours": None}},
        ]}

        response = client_explicable.post("/score-batch?explain=true", json=payload, headers=_headers())

        assert response.status_code == 200
        resultats = {r["client_id"]: r for r in response.json()["resultats"]}
        explication = resultats["CLI-1"]["explication"]
        assert explication["facteurs_hausse"][0]["variable"] == "derniere_connexion_jours"
        assert explication["facteurs_hausse"][0]["texte"].startswith("Jours depuis la dernière connexion : 115 j")
        assert explication["decision"].startswith(f"Priorité {resultats['CLI-1']['priorite']}")
        avertissements = " ".join(resultats["CLI-2"]["explication"]["avertissements"])
        assert "« Premium » inconnue du modèle" in avertissements and "manquante" in avertissements


class TestGardeFouBaseDeConnaissance:
    def test_ready_503_si_le_modele_contient_une_variable_exclue(self, artifacts_dir, client):
        (artifacts_dir / "model_manifest.json").write_text(
            json.dumps({"features": ["signal", "sante_compte_fin_periode"]}), encoding="utf-8")
        load_artifacts(artifacts_dir)

        response = client.get("/ready")

        assert response.status_code == 503
        assert "sante_compte_fin_periode" in response.json()["detail"]
