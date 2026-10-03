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

Explicabilité (`src/explain.py`) : `/score-batch?explain=true` ajoute à chaque compte les
facteurs qui augmentent et diminuent son risque, la trace de la règle de décision et les
avertissements sur ses valeurs d'entrée. Garde-fou : `/ready` répond 503 si le modèle chargé
contient une variable que la base de connaissance exclut (fuite, cible, leurre...).

Robustesse et sécurité (lot 3) :
- entrées validées (`src/validation.py`) : variable inconnue, type faux ou valeur physiquement
  impossible -> 422, avant tout calcul ;
- `/ready` répond 503 si l'empreinte SHA-256 d'un modèle chargé diffère de celle écrite par le
  notebook de certification (`model_manifest.json`, champ `empreintes_sha256`) : on ne sert pas
  un modèle autre que celui qui a été évalué ;
- sans variable d'environnement `API_KEY`, le service reste fermé (503 sur `/ready` et
  `/score-batch`) au lieu d'accepter une clé par défaut ; comparaison de la clé en temps constant.
"""
from __future__ import annotations

import hmac
import json
import logging
import os
import time
import uuid
from collections import defaultdict
from pathlib import Path

import joblib
import pandas as pd
import yaml
from fastapi import Depends, FastAPI, HTTPException, Request, Response, Security
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from pydantic import BaseModel, Field

from src.explain import (CHEMIN_BASE_DEFAUT, NOM_FICHIER_REFERENCE, charger_base_connaissance,
                         controler_exclusions, expliquer_batch)
from src.features import neutraliser_incoherences
from src.scoring import assigner_priorites, scorer_batch
from src.validation import valider_entrees
from src.versioning import sha256_of

app = FastAPI(title="Churn SaaS -- API de scoring")
logger = logging.getLogger("churn_saas.api")

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

MODEL_DIR = Path(os.getenv("MODEL_DIR", "data/model"))
KNOWLEDGE_PATH = Path(os.getenv("KNOWLEDGE_PATH", str(CHEMIN_BASE_DEFAUT)))
MAX_BODY_BYTES = int(os.getenv("MAX_BODY_BYTES", 256 * 1024))
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
RATE_LIMIT_WINDOW_SECONDS = 60

# Chargés une fois au démarrage ; None si les fichiers n'existent pas.
_model_churn = None
_model_clv = None
_feature_columns: list[str] = []
_seuil_d9: float = 0.0
_capacite_haute: int = 0
_reference_explication: dict | None = None
_base_connaissance: dict | None = None
_anomalies_bloquantes: list[dict] = []
_empreintes_non_conformes: list[str] = []   # modèles dont l'empreinte diffère de la certifiée
_empreintes_verifiees = False

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


def load_artifacts(model_dir: Path | None = None, knowledge_path: Path | None = None) -> None:
    """(Re)charge les modèles, la règle de décision D9/D10, la référence d'explication et la
    base de connaissance depuis disque. Ne lève jamais : laisse les artefacts à None si
    absents -- c'est `/ready` (ou `/score-batch?explain=true`) qui traduit ça en 503."""
    global _model_churn, _model_clv, _feature_columns, _seuil_d9, _capacite_haute
    global _reference_explication, _base_connaissance, _anomalies_bloquantes
    global _empreintes_non_conformes, _empreintes_verifiees

    model_dir = Path(model_dir) if model_dir else MODEL_DIR
    churn_path = model_dir / "model.joblib"
    clv_path = model_dir / "model_clv.joblib"
    manifest_path = model_dir / "scoring_manifest.json"
    model_manifest_path = model_dir / "model_manifest.json"

    _model_churn = joblib.load(churn_path) if churn_path.exists() else None
    _model_clv = joblib.load(clv_path) if clv_path.exists() else None

    manifeste_modele = {}
    if model_manifest_path.exists():
        with open(model_manifest_path, "r", encoding="utf-8") as f:
            manifeste_modele = json.load(f)
    _feature_columns = manifeste_modele.get("features", [])

    # Empreintes certifiées : écrites par le notebook de certification à côté des modèles qu'il
    # a évalués. Absentes d'un manifeste plus ancien : vérification impossible, signalée par /ready.
    certifiees = manifeste_modele.get("empreintes_sha256", {})
    _empreintes_verifiees = bool(certifiees)
    _empreintes_non_conformes = [
        nom for nom, attendue in certifiees.items()
        if not (model_dir / nom).exists() or sha256_of(model_dir / nom) != attendue
    ]

    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            regle = json.load(f)["regle_decision"]
        _seuil_d9 = float(regle["seuil_D9_valeur"])
        _capacite_haute = int(regle["capacite_csm_D10"])
    else:
        _seuil_d9, _capacite_haute = 0.0, 0

    reference_path = model_dir / NOM_FICHIER_REFERENCE
    if reference_path.exists():
        with open(reference_path, "r", encoding="utf-8") as f:
            _reference_explication = json.load(f)
    else:
        _reference_explication = None

    knowledge_path = Path(knowledge_path) if knowledge_path else KNOWLEDGE_PATH
    try:
        _base_connaissance = charger_base_connaissance(knowledge_path)
    except (OSError, yaml.YAMLError) as erreur:
        logger.warning("Base de connaissance illisible (%s) : explications et contrôles désactivés", erreur)
        _base_connaissance = None
    _anomalies_bloquantes = [
        a for a in (controler_exclusions(_feature_columns, _base_connaissance) if _base_connaissance else [])
        if a["gravite"] == "bloquant"
    ]


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


def _cle_configuree() -> str | None:
    return os.getenv("API_KEY") or None


def require_api_key(api_key: str = Security(_api_key_header)) -> str:
    attendue = _cle_configuree()
    if attendue is None:
        raise HTTPException(status_code=503, detail="Service fermé : API_KEY non configurée")
    if api_key is None or not hmac.compare_digest(api_key.encode("utf-8"), attendue.encode("utf-8")):
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
    client_id: str = Field(min_length=1, max_length=64)
    features: dict[str, float | str | None]


class ScoreBatchRequest(BaseModel):
    clients: list[ClientFeatures]


class Facteur(BaseModel):
    variable: str
    libelle: str
    valeur: float | str | None
    moyenne: float | None
    contribution: float
    texte: str


class Explication(BaseModel):
    facteurs_hausse: list[Facteur]
    facteurs_baisse: list[Facteur]
    decision: str
    avertissements: list[str]


class ScoredClient(BaseModel):
    client_id: str
    score_churn: float
    valeur_vie_estimee_eur: float
    perte_attendue_eur: float
    priorite: str
    action_recommandee: str
    explication: Explication | None = None


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
    """Le service peut vraiment scorer : les deux modèles et la règle D9/D10 sont chargés, ce
    sont ceux qui ont été certifiés, et une clé API est configurée."""
    if _cle_configuree() is None:
        raise HTTPException(status_code=503, detail="Service fermé : API_KEY non configurée")
    if _model_churn is None or _model_clv is None:
        raise HTTPException(status_code=503, detail="Modèles non chargés")
    if not _feature_columns:
        raise HTTPException(status_code=503, detail="Colonnes de features non chargées (model_manifest.json)")
    if _anomalies_bloquantes:
        variables = ", ".join(a["variable"] for a in _anomalies_bloquantes)
        raise HTTPException(status_code=503, detail=f"Modèle non conforme à la base de connaissance : {variables}")
    if _empreintes_non_conformes:
        raise HTTPException(status_code=503, detail="Empreinte différente du modèle certifié : "
                                                    + ", ".join(_empreintes_non_conformes))
    return {"status": "ready", "empreintes_verifiees": _empreintes_verifiees}


@app.post(
    "/score-batch",
    response_model=ScoreBatchResponse,
    # sans `explain`, le champ `explication` n'est pas renseigné : il est omis de la réponse
    response_model_exclude_unset=True,
    dependencies=[Depends(require_api_key), Depends(rate_limit_dependency)],
)
def score_batch(payload: ScoreBatchRequest, explain: bool = False):
    if _model_churn is None or _model_clv is None:
        raise HTTPException(status_code=503, detail="Modèles non chargés")
    if explain and (_reference_explication is None or _base_connaissance is None):
        raise HTTPException(status_code=503, detail="Explications indisponibles : référence ou base de connaissance absente")

    if not payload.clients:
        raise HTTPException(status_code=422, detail="clients ne peut pas être vide")
    erreurs = valider_entrees([(c.client_id, c.features) for c in payload.clients], _feature_columns)
    if erreurs:
        raise HTTPException(status_code=422, detail=erreurs)

    client_ids = pd.Series([c.client_id for c in payload.clients])
    X = pd.DataFrame([c.features for c in payload.clients]).reindex(columns=_feature_columns)
    X = neutraliser_incoherences(X)       # même règle qu'à l'entraînement (retards impossibles)

    resultats = scorer_batch(X, client_ids, _model_churn, _model_clv)
    resultats = assigner_priorites(resultats, seuil_d9=_seuil_d9, capacite_haute=_capacite_haute)

    _scoring_batch_size.observe(len(payload.clients))

    lignes = resultats[
        ["client_id", "score_churn", "valeur_vie_estimee_eur", "perte_attendue_eur", "priorite", "action_recommandee"]
    ].to_dict(orient="records")
    if explain:
        try:
            explications = expliquer_batch(_model_churn, X, resultats, _reference_explication, _base_connaissance,
                                           seuil_d9=_seuil_d9, capacite_haute=_capacite_haute)
        except (TypeError, ValueError) as erreur:
            raise HTTPException(status_code=503, detail=f"Explications indisponibles : {erreur}")
        for ligne, explication in zip(lignes, explications):
            ligne["explication"] = explication
    return ScoreBatchResponse(resultats=lignes)
