FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY scripts/start-api.sh /app/start-api.sh
RUN useradd -m scenthaus && mkdir -p /app/artifacts /app/state && chown -R scenthaus:scenthaus /app
USER scenthaus
ENV OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
EXPOSE 8000
CMD ["bash", "/app/start-api.sh"]
