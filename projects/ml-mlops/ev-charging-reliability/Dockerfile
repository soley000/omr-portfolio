# Image de l'API ChargeTriage : le code et ses dépendances, sans données ni modèle.
# Le paquet (modèle + variables) est fourni au lancement : docker run -v .../bundle:/app/bundle
ARG PYTHON_VERSION=3.10
FROM python:${PYTHON_VERSION}-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MLFLOW_DISABLE_AGENT_HINT=1 \
    EVREL_BUNDLE_DIR=/app/bundle

# 1. Les dépendances d'abord : cette étape reste en cache tant que la liste ne change pas.
COPY requirements-docker.txt .
RUN pip install --no-cache-dir -r requirements-docker.txt

# 2. Le code du projet (paquet evrel, puis l'API).
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir --no-deps .
COPY api/ api/

# 3. Sécurité : l'API ne tourne pas en administrateur.
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]