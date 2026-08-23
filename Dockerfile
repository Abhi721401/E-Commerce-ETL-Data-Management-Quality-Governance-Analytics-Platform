# Dockerfile
# ---------------------------------------------------------------------
# Container image for the ETL / data-quality application. This image
# runs the pipeline (src/reporting.py::run_full_pipeline) and can also
# be used as the base image for local ad-hoc runs of individual stages.
# ---------------------------------------------------------------------

FROM python:3.11-slim

WORKDIR /app

# System dependencies for psycopg2 / postgres client tools
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

CMD ["python", "-m", "src.reporting"]
