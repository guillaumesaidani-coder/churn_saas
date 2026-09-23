# syntax=docker/dockerfile:1

# Deux cibles :
#   runtime  -> API de scoring + exporteur de dérive (image légère, requirements.txt)
#   pipeline -> rejoue le pipeline DVC (notebooks, entraînement, MLflow, tests) ;
#               le code et les données sont montés en volume, pas copiés.
# compose.yaml choisit la cible de chaque service (`build.target`).

FROM python:3.13-slim AS pipeline
WORKDIR /app
ENV MLFLOW_DISABLE_AGENT_HINT=1     PYTHONIOENCODING=utf-8
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
CMD ["python", "-m", "dvc", "repro"]


FROM python:3.13-slim AS runtime
WORKDIR /app

RUN groupadd --system appgroup \
    && useradd --system --uid 10001 --gid appgroup --no-create-home appuser

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY scripts ./scripts
COPY data/model ./data/model
COPY data/gold ./data/gold

RUN mkdir -p /app && chown -R appuser:appgroup /app
USER appuser

EXPOSE 8000

# Pas de curl/wget dans python:3.13-slim (les ajouter grossirait l'image) : la sonde
# utilise le stdlib déjà présent.
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=2)" || exit 1

CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
