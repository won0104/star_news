# AI CPU inference runtime. Model weights are mounted via volume later.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HUB_OFFLINE=0 \
    TRANSFORMERS_OFFLINE=0

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

CMD ["python", "-c", "import torch, transformers; print(torch.__version__); print('cuda', torch.cuda.is_available()); print('transformers', transformers.__version__)"]
