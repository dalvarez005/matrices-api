# syntax=docker/dockerfile:1
# API de matrices: FastAPI + RapidOCR (OCR de fotos). Ver docs/DEPLOY.md.
FROM python:3.13-slim

# OpenMP para onnxruntime (OCR).
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Dependencias primero: quedan en caché mientras no cambie uv.lock.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project \
 && .venv/bin/python -c "from rapidocr import RapidOCR; RapidOCR()"
# (lo anterior descarga los modelos del OCR dentro de la imagen)
COPY README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

RUN useradd --system --uid 1654 app \
 && mkdir -p /data/apk && chown -R app /data
# APK publicado: fuera de la imagen, en un volumen.
VOLUME /data
USER app
ENV PATH="/app/.venv/bin:$PATH" DATA_DIR=/data
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health').status == 200 else 1)"

# Un proceso alcanza (y la Orange Pi tiene poca memoria); el OCR se limita aparte.
CMD ["uvicorn", "matrices_api.app:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]
