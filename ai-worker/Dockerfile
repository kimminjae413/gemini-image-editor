# RunPod AI Hair Transfer Worker Dockerfile
FROM nvidia/cuda:12.1-devel-ubuntu22.04

# 환경 변수 설정
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 기본 패키지 설치
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    git \
    wget \
    curl \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libgtk-3-dev \
    && rm -rf /var/lib/apt/lists/*

# Python 별칭 설정
RUN ln -s /usr/bin/python3 /usr/bin/python

# pip 업그레이드
RUN pip install --upgrade pip

# 작업 디렉토리 설정
WORKDIR /app

# Python 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# AI 모델 가중치 다운로드
RUN mkdir -p /weights

# GFPGAN 모델 다운로드
RUN wget -O /weights/GFPGANv1.4.pth \
    https://github.com/TencentARC/GFPGAN/releases/download/v1.3.4/GFPGANv1.4.pth

# Real-ESRGAN 모델 다운로드  
RUN wget -O /weights/RealESRGAN_x2plus.pth \
    https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth

# Stable Diffusion 모델 사전 다운로드 (컨테이너 빌드시)
RUN python -c "
from diffusers import StableDiffusionXLInpaintPipeline
import torch
print('Downloading Stable Diffusion XL Inpainting model...')
pipe = StableDiffusionXLInpaintPipeline.from_pretrained(
    'diffusers/stable-diffusion-xl-1.0-inpainting-0.1',
    torch_dtype=torch.float16,
    use_safetensors=True,
    variant='fp16'
)
print('Model download completed!')
"

# 메인 핸들러 파일 복사
COPY handler.py .

# 헬스체크 스크립트
RUN echo '#!/bin/bash\npython -c "import torch; print(f\"CUDA available: {torch.cuda.is_available()}\"); print(f\"GPU count: {torch.cuda.device_count()}\")"' > /healthcheck.sh
RUN chmod +x /healthcheck.sh

# GPU 메모리 최적화 환경 변수
ENV PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512

# RunPod 포트 설정
EXPOSE 8000

# 헬스체크 설정
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD /healthcheck.sh

# 메인 핸들러 실행
CMD ["python", "handler.py"]
