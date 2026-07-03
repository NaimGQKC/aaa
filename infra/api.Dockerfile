FROM python:3.12-slim

# WeasyPrint system deps (PDF export); keep image otherwise minimal.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
    fonts-dejavu-core shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY packages/schemas packages/schemas
COPY api api
COPY workers workers
COPY scripts scripts

RUN pip install --no-cache-dir -e packages/schemas -e "api[postgres,s3,mistral,reports]"

ENV PYTHONPATH=/srv/api:/srv/packages/schemas:/srv/scripts
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--app-dir", "api", "--host", "0.0.0.0", "--port", "8000"]
