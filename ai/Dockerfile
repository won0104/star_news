# AI CPU inference runtime. Model weights are mounted via volume later.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    KG_MODEL_DIR=/models/artifacts/kg-extractor \
    ARTICLELOCAL_HF_CACHE=/models/cache/hub \
    HF_HUB_CACHE=/models/cache/hub

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Torch must come from the CPU index so a CUDA wheel is not pulled by mistake.
RUN pip install --no-cache-dir \
    torch==2.6.0+cpu \
    --index-url https://download.pytorch.org/whl/cpu

COPY requirements-cpu.txt .
RUN pip install --no-cache-dir -r requirements-cpu.txt

COPY starlight_ai ./starlight_ai

EXPOSE 8100

# 프로세스를 늘리면 프로세스마다 모델 전체가 RAM에 중복 적재된다.
# 단일 worker 안에서 server.py의 analyzer 하나를 계속 재사용한다.
CMD ["uvicorn", "starlight_ai.server:app", "--host", "0.0.0.0", "--port", "8100", "--workers", "1"]
