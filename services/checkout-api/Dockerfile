# syntax=docker/dockerfile:1.7
# Multi-stage, non-root, read-only-rootfs friendly image.
FROM python:3.12-slim AS build
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim AS runtime
ARG APP_VERSION=dev
ARG BUILD_ID=local
LABEL org.opencontainers.image.source="https://github.com/JoshilFernandes/sentinel-slo-platform" \
      org.opencontainers.image.title="checkout-api" \
      org.opencontainers.image.version="${APP_VERSION}"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    APP_VERSION=${APP_VERSION} BUILD_ID=${BUILD_ID}
COPY --from=build /install /usr/local
WORKDIR /srv
COPY app ./app
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app
USER 10001
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=2s CMD python -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz',timeout=2).status==200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
