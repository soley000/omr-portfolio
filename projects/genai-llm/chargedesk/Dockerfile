# ChargeDesk : image de l'API (page + assistant), donnees comprises.
#
# Construction (les donnees viennent du dossier de donnees, jamais du depot Git) :
#   docker build --build-context data=C:\dev\chargedesk-data -t chargedesk .
# Lancement local (cles lues dans .env, jamais copiees dans l'image) :
#   docker run --rm -p 8000:8000 --env-file .env chargedesk
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

LABEL org.opencontainers.image.title="ChargeDesk" \
      org.opencontainers.image.description="Assistant de la tournee du soir : agent LLM a outils sur les donnees ChargeTriage" \
      org.opencontainers.image.source="https://github.com/soley000/omr-portfolio" \
      data.source="Jiaxing EV charging dataset, Zhang et al. 2025, Scientific Data, doi:10.6084/m9.figshare.28182251.v3" \
      data.license="CC BY 4.0"

WORKDIR /app

# 1) Dependances d'abord : cette couche reste en cache tant que les versions ne changent pas
COPY requirements-docker.txt requirements.txt ./
RUN pip install -r requirements-docker.txt -c requirements.txt

# 2) Le code
COPY configs/ configs/
COPY src/ src/
COPY api/ api/

# 3) Les donnees : l'entrepot (lecture seule) et les reponses preparees
COPY --from=data chargedesk.duckdb /data/chargedesk.duckdb
COPY --from=data demo/prepared.json /data/demo/prepared.json

# 4) Utilisateur sans droits d'administration ; seuls le cache des appels LLM et le journal sont inscriptibles
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /data/llm_cache /data/monitoring \
    && chown -R app /data/llm_cache /data/monitoring

ENV PYTHONPATH=/app/src:/app \
    CHARGEDESK_DATA_DIR=/data
USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT', '8000'), timeout=4)"

# Render fournit le port dans $PORT ; 8000 en local
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
