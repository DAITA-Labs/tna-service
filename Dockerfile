FROM python:3.12-slim

WORKDIR /app

# Install pip deps from pyproject.toml directly (no editable install in image).
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
        haystack-ai>=2.10 fastapi>=0.110 "uvicorn[standard]>=0.27" \
        pydantic>=2.6 pydantic-settings>=2.2 python-dotenv>=1.0 \
        anthropic>=0.49 openpyxl==3.1.5 structlog>=24.1 \
        prometheus-client>=0.20 starlette-prometheus>=0.10 pyyaml>=6.0

COPY app ./app
COPY evals ./evals
COPY scripts ./scripts

ENV PYTHONPATH=/app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
