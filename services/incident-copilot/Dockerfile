# syntax=docker/dockerfile:1.7
# Build context is the repo root so the runbooks ship inside the image.
FROM python:3.12-slim AS build
WORKDIR /build
COPY services/incident-copilot/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim AS runtime
LABEL org.opencontainers.image.source="https://github.com/marwin226/sentinel-slo-platform" \
      org.opencontainers.image.title="incident-copilot"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 RUNBOOK_DIR=/srv/runbooks
COPY --from=build /install /usr/local
WORKDIR /srv
COPY services/incident-copilot/app ./app
COPY docs/runbooks ./runbooks
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
USER 10001
EXPOSE 8081
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8081", "--no-access-log"]
