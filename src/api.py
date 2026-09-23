"""API de scoring churn SaaS : `/health`, `/ready`, `/metrics`, `/score-batch`.

Portée du mécanisme de service de `py-init/ml/src/indusense/api/main.py` (mêmes contrôles :
auth par clé API, limite de débit, limite de taille de payload, identifiant de requête,
instrumentation Prometheus) -- adaptée au scoring churn+CLV (`src/scoring.py`) au lieu du
pipeline sklearn unique d'InduSense : deux modèles chargés (`model.joblib`, `model_clv.joblib`)
et la règle de décision D9/D10/D14 (seuil + capacité CSM, figés dans
`data/model/scoring_manifest.json`, jamais recalculés au moment du scoring réel -- voir
`src/scoring.py::calibrer_seuil_d9`).

Aucune nouvelle logique de scoring : `/score-batch` appelle `src.scoring.scorer_batch` et
`assigner_priorites`, déjà testés indépendamment de l'API (`tests/test_scoring.py`).
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from collections import defaultdict
from pathlib import Path

import joblib
import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Request, Response, Security
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel

from src.scoring import assigner_priorites, scorer_batch

app = FastAPI(title="Churn SaaS -- API de scoring")
logger = logging.getLogger("churn_saas.api")

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

MODEL_DIR = Path(os.getenv("MODEL_DIR", "data/model"))
MAX_BODY_BYTES = int(os.getenv("MAX_BODY_BYTES", 256 * 1024))
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
RATE_LIMIT_WINDOW_SECONDS = 60

# Chargés une fois au démarrage ; None si les fichiers n'existent pas.
_model_churn = None
_model_clv = None
_feature_columns: list[str] = []
_seuil_d9: float = 0.0
_capacite_haute: int = 0

# IP -> horodatages des appels dans la fenêtre courante. En mémoire, par process : suffisant
# pour une seule instance, pas pour un déploiement multi-instance.
_rate_limit_state: dict[str, list[float]] = defaultdict(list)

_http_requests_total = Counter(
    "churn_saas_http_requests_total",
    "Nombre de requêtes HTTP reçues",
    ["method", "path", "status"],
)
_http_request_duration_seconds = Histogram(
    "churn_saas_http_request_duration_seconds",
    "Durée des requêtes HTTP",
    ["method", "path"],
)
_scoring_batch_size = Histogram(
    "churn_saas_scoring_batch_size",
    "Nombre de comptes scorés par appel à /score-batch",
)


def load_artifacts(model_dir: Path | None = None) -> None:
    """(Re)charge les modèles et la règle de décision D9/D10 depuis disque. Ne lève jamais :
    laisse les artefacts à None si absents -- c'est `/ready` qui traduit ça en 503."""
    global _model_churn, _model_clv, _feature_columns, _seuil_d9, _capacite_haute

    model_dir = Path(model_dir) if model_dir else MODEL_DIR
    churn_path = model_dir / "model.joblib"
    clv_path = model_dir / "model_clv.joblib"
    manifest_path = model_dir / "scoring_manifest.json"
    model_manifest_path = model_dir / "model_manifest.json"

    _model_churn = joblib.load(churn_path) if churn_path.exists() else None
    _model_clv = joblib.load(clv_path) if clv_path.exists() else None

    if model_manifest_path.exists():
        with open(model_manifest_path, "r", encoding="utf-8") as f:
            _feature_columns = json.load(f)["features"]
    else:
        _feature_columns = []

    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            regle = json.load(f)["regle_decision"]
        _seuil_d9 = float(regle["seuil_D9_valeur"])
        _capacite_haute = int(regle["capacite_csm_D10"])
    else:
        _seuil_d9, _capacite_haute = 0.0, 0


load_artifacts()


@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            length = int(content_length)
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Content-Length illisible"})
        if length > MAX_BODY_BYTES:
            return JSONResponse(
                status_code=413,
                content={"detail": f"Payload supérieur à {MAX_BODY_BYTES} octets"},
            )
    return await call_next(request)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    start = time.monotonic()
    response = await call_next(request)
    duration = time.monotonic() - start
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_id=%s method=%s path=%s status=%s",
        request_id, request.method, request.url.path, response.status_code,
    )
    _http_requests_total.labels(
        method=request.method, path=request.url.path, status=response.status_code
    ).inc()
    _http_request_duration_seconds.labels(method=request.method, path=request.url.path).observe(duration)
    return response


def require_api_key(api_key: str = Security(_api_key_header)) -> str:
    expected = os.getenv("API_KEY", "dev-local-key")
    if api_key != expected:
        raise HTTPException(status_code=401, detail="Clé API manquante ou invalide")
    return api_key


def rate_limit(client_id: str) -> None:
    now = time.monotonic()
    window_start = now - RATE_LIMIT_WINDOW_SECONDS
    timestamps = _rate_limit_state[client_id]
    while timestamps and timestamps[0] < window_start:
        timestamps.pop(0)
    if len(timestamps) >= RATE_LIMIT_PER_MINUTE:
        raise HTTPException(status_code=429, detail="Trop de requêtes -- réessayez plus tard")
    timestamps.append(now)


def rate_limit_dependency(request: Request) -> None:
    client_id = request.client.host if request.client else "unknown"
    rate_limit(client_id)


class ClientFeatures(BaseModel):
    client_id: str
    features: dict[str, float | str | None]


class ScoreBatchRequest(BaseModel):
    clients: list[ClientFeatures]


class ScoredClient(BaseModel):
    client_id: str
    score_churn: float
    valeur_vie_estimee_eur: float
    perte_attendue_eur: float
    priorite: str
    action_recommandee: str


class ScoreBatchResponse(BaseModel):
    resultats: list[ScoredClient]


@app.get("/metrics")
def metrics():
    """Scrapé par Prometheus (voir prometheus.yml, job churn-saas-api)."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
def health():
    """Le processus tourne -- ne dit rien des modèles. Pas d'authentification : une sonde
    de liveness ne doit jamais dépendre d'une clé API."""
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """Le service peut vraiment scorer : les deux modèles et la règle D9/D10 sont chargés."""
    if _model_churn is None or _model_clv is None:
        raise HTTPException(status_code=503, detail="Modèles non chargés")
    if not _feature_columns:
        raise HTTPException(status_code=503, detail="Colonnes de features non chargées (model_manifest.json)")
    return {"status": "ready"}


@app.post(
    "/score-batch",
    response_model=ScoreBatchResponse,
    dependencies=[Depends(require_api_key), Depends(rate_limit_dependency)],
)
def score_batch(payload: ScoreBatchRequest):
    if _model_churn is None or _model_clv is None:
        raise HTTPException(status_code=503, detail="Modèles non chargés")

    if not payload.clients:
        raise HTTPException(status_code=422, detail="clients ne peut pas être vide")

    client_ids = pd.Series([c.client_id for c in payload.clients])
    X = pd.DataFrame([c.features for c in payload.clients]).reindex(columns=_feature_columns)

    resultats = scorer_batch(X, client_ids, _model_churn, _model_clv)
    resultats = assigner_priorites(resultats, seuil_d9=_seuil_d9, capacite_haute=_capacite_haute)

    _scoring_batch_size.observe(len(payload.clients))

    return ScoreBatchResponse(resultats=resultats[
        ["client_id", "score_churn", "valeur_vie_estimee_eur", "perte_attendue_eur", "priorite", "action_recommandee"]
    ].to_dict(orient="records"))
