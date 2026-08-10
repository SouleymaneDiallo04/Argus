FROM python:3.12-slim
WORKDIR /app
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt ./requirements.txt
# torch CPU d'abord -> ultralytics le voit satisfait (évite le wheel CUDA ~2 Go)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY best.pt /app/best.pt
RUN mkdir -p /data
ENV ARGUS_MODEL_PATH=/app/best.pt \
    ARGUS_DB_PATH=/data/argus.db \
    ARGUS_SNAPSHOT_DIR=/data/snapshots
EXPOSE 8000
CMD ["uvicorn", "--factory", "app.api.app:create_app", "--host", "0.0.0.0", "--port", "8000"]
