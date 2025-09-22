#!/usr/bin/env python3
"""
AI Hair Style Transfer - RunPod Worker Handler
ComfyUI 스타일 고품질 후보정이 포함된 AI 헤어 변경 처리
"""

import runpod
import torch
import numpy as np
import cv2
from PIL import Image, ImageOps
import requests
import io
import boto3
import logging
import traceback
from datetime import datetime
from typing import Tuple, Optional

# Diffusers 및 AI 모델 import
from diffusers import StableDiffusionXLInpaintPipeline, ControlNetModel
from transformers import pipeline
import scipy.ndimage

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 글로벌 변수로 모델들 저장 (컨테이너 시작시 한번만 로드)
pipe = None
face_enhancer = None
upscaler = None

def initialize_models():
    """AI 모델들 초기화 (컨테이너 시작시 실행)"""
    global pipe, face_enhancer, upscaler
    
    try:
        logger.info("AI 모델 로딩 시작...")
        
        # 1. Stable Diffusion XL Inpainting 파이프라인
        logger.info("Stable Diffusion XL Inpainting 로딩...")
        pipe = StableDiffusionXLInpaintPipeline.from_pretrained(
            "diffusers/stable-diffusion-xl-1.0-inpainting-0.1",
            torch_dtype=torch.float16,
            use_safetensors=True,
            variant="fp16"
        )
        pipe.to("cuda")
        pipe.enable_xformers_memory_efficient_attention()
        pipe.enable_vae_tiling()  # 메모리 효율성 향상
        
        # 2. Face Enhancement 모델 로딩 시도
        try:
            from gfpgan import GFPGANer
            from basicsr.archs.rrdbnet_arch import RRDBNet
            from realesrgan import RealESRGANer
            
            # GFPGAN 얼굴 복원
            logger.info("GFPGAN 얼굴 복원 모델 로딩...")
            face_enhancer = GFPGANer(
                model_path='/weights/GFPGANv1.4.pth',
                upscale=1,
                arch='clean', 
                channel_multiplier=2,
                bg_upsampler=None
            )
            
            # Real-ESRGAN 업스케일러
            logger.info("Real-ESRGAN 업스케일러 로딩...")
            model = RRDBNet(
                num_in_ch=3, num_out_ch=3, num_feat=64, 
                num_block=23, num_grow_ch=32, scale=2
            )
            upscaler = RealESRGANer(
                scale=2,
                model_path='/weights/RealESRGAN_x2plus.pth',
                model=model,
                tile=400,
                tile_pad=10,
                pre_pad=0,
                half=True  # FP16으로 메모리 절약
            )
            
        except ImportError as e:
            logger.warning(f"고급 후보정 모델 로딩 실패: {e}")
            logger.info("기본 후보정을 사용합니다")
            face_enhancer = None
            upscaler = None
        
        logger.info("모든 AI 모델 로딩 완료!")
        return True
        
    except Exception as e:
        logger.error(f"모델 초기화 실패: {e}")
        logger.error(traceback.format_exc())
        return False

def download_image_from_url(url: str) -> Image.Image:
    """URL에서 이미지 다운로드"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return Image.open(io.BytesIO(response.content)).convert("RGB")
    except Exception as e:
        logger.error(f"이미지 다운로드 실패 {url}: {e}")
        raise

def preprocess_mask(mask_image: Image.Image) -> Image.Image:
    """마스크 이미지 전처리"""
    # 그레이스케일로 변환
    if mask_image.mode != 'L':
        mask_image = mask_image.convert('L')
    
    # 이진화 처리 (흰색=마스킹 영역, 검은색=보존 영역)
    mask_array = np.array(mask_image)
    
    # 색상이 있는 부분을 흰색으로, 없는 부분을 검은색으로
    mask_binary = np.where(mask_array > 50, 255, 0).astype(np.uint8)
    
    # 모폴로지 연산으로 마스크 정리
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask_binary = cv2.morphologyEx(mask_binary, cv2.MORPH_CLOSE, kernel)
    mask_binary = cv2.morphologyEx(mask_binary, cv2.MORPH_OPEN, kernel)
    
    # 가우시안 블러로 경계 부드럽게
    mask_binary = cv2.GaussianBlur(mask_binary, (5, 5), 0)
    
    return Image.fromarray(mask_binary, mode='L')

def extract_hair_features(reference_image: Image.Image, reference_mask: Image.Image) -> Image.Image:
    """참조 이미지에서 헤어 특징 추출"""
    ref_array = np.array(reference_image)
    mask_array = np.array(reference_mask) / 255.0
    
    # 마스크 적용하여 헤어 영역만 추출
    if len(mask_array.shape) == 2:
        mask_array = np.stack([mask_array] * 3, axis=2)
    
    # 헤어 영역 추출
    hair_region = ref_array * mask_array
    
    # 배경을 자연스럽게 블렌딩
    background = np.ones_like(ref_array) * 128  # 회색 배경
    result = hair_region + background * (1 - mask_array)
    
    return Image.fromarray(result.astype(np.uint8))

def apply_face_restoration(image: Image.Image) -> Image.Image:
    """GFPGAN을 이용한 얼굴 복원"""
    if face_enhancer is None:
        return apply_fallback_face_enhancement(image)
    
    try:
        img_array = np.array(image)
        _, _, restored_img = face_enhancer.enhance(
            img_array, 
            has_aligned=False, 
            only_center_face=False, 
            paste_back=True,
            weight=0.7  # 자연스러운 블렌딩
        )
        return Image.fromarray(restored_img)
        
    except Exception as e:
        logger.warning(f"GFPGAN 처리 실패, 대체 방법 사용: {e}")
        return apply_fallback_face_enhancement(image)

def apply_fallback_face_enhancement(image: Image.Image) -> Image.Image:
    """GFPGAN 대체용 얼굴 향상"""
    img_array = np.array(image)
    
    # 얼굴 영역 대략적 추정 (중앙 상단 부분)
    h, w = img_array.shape[:2]
    face_center_y, face_center_x = int(h * 0.35), int(w * 0.5)
    face_radius = min(h, w) // 5
    
    # 얼굴 마스크 생성
    y, x = np.ogrid[:h, :w]
    face_mask = ((y - face_center_y)**2 + (x - face_center_x)**2) <= face_radius**2
    face_mask = scipy.ndimage.gaussian_filter(face_mask.astype(float), sigma=15)
    face_mask = np.stack([face_mask] * 3, axis=2)
    
    # 얼굴 영역 부드럽게 처리
    smoothed = cv2.bilateralFilter(img_array, 15, 50, 50)
    enhanced = img_array * (1 - face_mask * 0.4) + smoothed * (face_mask * 0.4)
    
    return Image.fromarray(enhanced.astype(np.uint8))

def apply_final_upscaling(image: Image.Image) -> Image.Image:
    """Real-ESRGAN을 이용한 최종 품질 향상"""
    if upscaler is None:
        return apply_fallback_enhancement(image)
    
    try:
        img_array = np.array(image)
        enhanced_array, _ = upscaler.enhance(img_array, outscale=1.0)
        return Image.fromarray(enhanced_array)
        
    except Exception as e:
        logger.warning(f"Real-ESRGAN 처리 실패, 대체 방법 사용: {e}")
        return apply_fallback_enhancement(image)

def apply_fallback_enhancement(image: Image.Image) -> Image.Image:
    """Real-ESRGAN 대체용 이미지 향상"""
    img_array = np.array(image)
    
    # 언샤프 마스킹
    blur = cv2.GaussianBlur(img_array, (0, 0), 1.0)
    unsharp = cv2.addWeighted(img_array, 1.3, blur, -0.3, 0)
    
    # 대비 향상 (CLAHE)
    lab = cv2.cvtColor(unsharp, cv2.COLOR_RGB2LAB)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    lab[:, :, 0] = clahe.apply(lab[:, :, 0])
    final = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
    
    return Image.fromarray(final)

def blend_result_with_original(result: Image.Image, original: Image.Image, mask: Image.Image) -> Image.Image:
    """결과를 원본과 자연스럽게 블렌딩"""
    result_array = np.array(result)
    original_array = np.array(original)
    mask_array = np.array(mask) / 255.0
    
    # 마스크 경계를 부드럽게 만들기
    smooth_mask = cv2.GaussianBlur(mask_array.astype(np.float32), (21, 21), 0)
    
    if len(smooth_mask.shape) == 2:
        smooth_mask = np.stack([smooth_mask] * 3, axis=2)
    
    # 부드러운 알파 블렌딩
    blended = (result_array * smooth_mask + 
               original_array * (1 - smooth_mask)).astype(np.uint8)
    
    return Image.fromarray(blended)

def upload_result_to_s3(result_image: Image.Image, job_id: str) -> str:
    """결과 이미지를 S3에 업로드"""
    try:
        # 이미지를 바이트 버퍼로 변환
        img_buffer = io.BytesIO()
        result_image.save(img_buffer, format='PNG', quality=95)
        img_buffer.seek(0)
        
        # S3 업로드
        s3_client = boto3.client('s3')
        bucket_name = "hair-transfer-storage"  # 환경변수로 관리 권장
        key = f"results/{job_id}_result.png"
        
        s3_client.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=img_buffer.getvalue(),
            ContentType="image/png",
            ACL='public-read'
        )
        
        result_url = f"https://{bucket_name}.s3.ap-northeast-2.amazonaws.com/{key}"
        logger.info(f"결과 이미지 S3 업로드 완료: {result_url}")
        
        return result_url
        
    except Exception as e:
        logger.error(f"S3 업로드 실패: {e}")
        # 개발 환경에서는 로컬 URL 반환
        return f"local://results/{job_id}_result.png"

def handler(event):
    """RunPod 메인 핸들러 함수"""
    try:
        start_time = datetime.now()
        input_data = event["input"]
        job_id = input_data["job_id"]
        
        logger.info(f"Job {job_id}: 처리 시작")
        
        # 1. 이미지들 다운로드
        logger.info(f"Job {job_id}: 이미지 다운로드 중...")
        seed_image = download_image_from_url(input_data["seed_image_url"])
        seed_mask = download_image_from_url(input_data["seed_mask_url"])
        ref_image = download_image_from_url(input_data["reference_image_url"])
        ref_mask = download_image_from_url(input_data["reference_mask_url"])
        
        # 2. 이미지 크기 통일 (1024x1024)
        target_size = (1024, 1024)
        seed_image = seed_image.resize(target_size, Image.LANCZOS)
        ref_image = ref_image.resize(target_size, Image.LANCZOS)
        
        # 3. 마스크 전처리
        logger.info(f"Job {job_id}: 마스크 전처리 중...")
        seed_mask = preprocess_mask(seed_mask.resize(target_size, Image.LANCZOS))
        ref_mask = preprocess_mask(ref_mask.resize(target_size, Image.LANCZOS))
        
        # 4. 참조 헤어 특징 추출
        hair_features = extract_hair_features(ref_image, ref_mask)
        
        # 5. 프롬프트 생성
        prompt = """
        high quality portrait, natural hair texture, seamless hair integration, 
        professional photography, detailed hair strands, realistic lighting,
        photorealistic, 8k resolution, beautiful hair, perfect blend
        """
        
        negative_prompt = """
        blurry, distorted, unnatural hair, artificial looking, low quality,
        artifacts, seams, mismatched colors, cartoon, anime, painting,
        deformed, ugly, bad anatomy, extra limbs
        """
        
        # 6. Stable Diffusion XL Inpainting 실행
        logger.info(f"Job {job_id}: AI 이미지 생성 중...")
        with torch.cuda.amp.autocast():
            result = pipe(
                prompt=prompt,
                negative_prompt=negative_prompt,
                image=seed_image,
                mask_image=seed_mask,
                num_inference_steps=30,  # 품질과 속도 밸런스
                guidance_scale=7.5,
                strength=0.95,
                generator=torch.Generator("cuda").manual_seed(42)
            ).images[0]
        
        # 7. ComfyUI 스타일 고급 후보정
        logger.info(f"Job {job_id}: 후보정 처리 중...")
        
        # 7-1. 얼굴 복원
        result = apply_face_restoration(result)
        
        # 7-2. 최종 품질 향상
        result = apply_final_upscaling(result)
        
        # 7-3. 원본과 자연스럽게 블렌딩
        result = blend_result_with_original(result, seed_image, seed_mask)
        
        # 8. 결과 이미지 업로드
        logger.info(f"Job {job_id}: 결과 업로드 중...")
        result_url = upload_result_to_s3(result, job_id)
        
        # 9. 처리 시간 계산
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        logger.info(f"Job {job_id}: 처리 완료 ({processing_time:.1f}초)")
        
        return {
            "status": "success",
            "result_url": result_url,
            "job_id": job_id,
            "processing_time": processing_time,
            "timestamp": end_time.isoformat()
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Job {job_id}: 처리 실패 - {error_msg}")
        logger.error(traceback.format_exc())
        
        return {
            "status": "error",
            "error": error_msg,
            "job_id": job_id if 'job_id' in locals() else "unknown",
            "timestamp": datetime.now().isoformat()
        }

# RunPod 서버리스 시작
if __name__ == "__main__":
    # 모델 초기화
    if initialize_models():
        logger.info("RunPod 워커 시작")
        runpod.serverless.start({"handler": handler})
    else:
        logger.error("모델 초기화 실패, 워커 시작 불가")
        exit(1)
