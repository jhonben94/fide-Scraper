# Stage 1: Builder
FROM python:3.12-slim as builder

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir --target=/app/deps -r requirements.txt

# Stage 2: Runtime
FROM python:3.12-slim as runtime

RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copiar dependencias del builder
COPY --from=builder /app/deps /app/deps
ENV PYTHONPATH=/app:/app/deps
ENV PATH="/app/deps/bin:$PATH"

# Copiar código
COPY src/ /app/src/
COPY scripts/ /app/scripts/

# Directorios para datos
RUN mkdir -p /data/exports && chown -R appuser:appuser /data

USER appuser

# Por defecto ejecutar API; para import: docker run ... python -m scripts.run_import
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
