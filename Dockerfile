FROM python:3.12-slim

WORKDIR /app

# Copy pyproject.toml first so the dep layer caches independently of source.
# A README.md is required by setuptools for `pip install .` even though we
# only want the deps (the project itself gets re-bound via PYTHONPATH below).
COPY pyproject.toml README.md ./

# Install dependencies straight from pyproject.toml's [project].dependencies.
# `pip install --no-deps .` would skip them; we want full resolution. The
# resulting site-packages owns app/ via the install metadata, but at runtime
# we use PYTHONPATH so app/ updates in COPY land immediately.
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir .

COPY app ./app
COPY evals ./evals
COPY scripts ./scripts

# Local dataset is mounted via docker-compose volume, but bake the dir so the
# package can resolve `app/...` imports without compose.
ENV PYTHONPATH=/app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
