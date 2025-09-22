#!/usr/bin/env python3
"""
AI Hair Style Transfer - Backend API Server
FastAPI 기반 헤어 스타일 변경 서비스 백엔드
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import runpod
import boto3
import redis
import uuid
import asyncio
import os
import json
import logging
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from PIL import Image
import io
import base64

# 환경변수 로드
from dotenv import load_dotenv
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI 앱 초기화
app = FastAPI(
    title="AI Hair Style Transfer API",
    description="마스킹 기반 AI 헤어 스타일 변경 서비스",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인만 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 제공 (프론트엔드)
app.mount("/static", StaticFiles(directory="../"), name="static")

# 환경 변수 설정
RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY")
RUNPOD_ENDPOINT = os.getenv("RUNPOD_ENDPOINT")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_BUCKET_NAME = os.getenv("AWS_BUCKET_NAME", "hair-transfer-storage")
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-2")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# 서비스 클라이언트 초기화
try:
    runpod.api_key = RUNPOD_API_KEY
    
    # AWS S3 클라이언트
    s3_client = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION
    )
    
    # Redis 클라이언트
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    
    logger.info("모든 서비스 클라이언트 초기화 완료")
    
except Exception as e:
    logger.error(f"서비스 초기화 실패: {e}")
    # 개발 환경에서는 None으로 설정하여 로컬 테스트 가능
    s3_client = None
    redis_client = None

# 데이터 모델
class JobStatus(BaseModel):
    job_id: str
    status: str  # PENDING, PROCESSING, COMPLETED, FAILED
    progress: Optional[str] = None
    result_url: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class TransferRequest(BaseModel):
    job_id: str
    seed_image_url: str
    seed_mask_url: str
    reference_image_url: str
    reference_mask_url: str

# 헬스 체크
@app.get("/")
async def root():
    """프론트엔드 index.html 반환"""
    return FileResponse("../index.html")

@app.get("/health")
async def health_check():
    """서비스 상태 확인"""
    services_status = {
        "api": "healthy",
        "runpod": "connected" if RUNPOD_API_KEY else "not_configured",
        "s3": "connected" if s3_client else "not_configured", 
        "redis": "connected" if redis_client else "not_configured",
        "timestamp": datetime.now().isoformat()
    }
    
    # Redis 연결 테스트
    if redis_client:
        try:
            redis_client.ping()
            services_status["redis"] = "healthy"
        except:
            services_status["redis"] = "error"
    
    return services_status

# 파일 업로드 유틸리티
async def upload_to_s3(file_content: bytes, key: str, content_type: str) -> str:
    """S3에 파일 업로드하고 URL 반환"""
    if not s3_client:
        # 로컬 개발용: 임시 URL 반환
        return f"local://temp/{key}"
    
    try:
        s3_client.put_object(
            Bucket=AWS_BUCKET_NAME,
            Key=key,
            Body=file_content,
            ContentType=content_type,
            ACL='public-read'  # 공개 읽기 권한
        )
        
        url = f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{key}"
        logger.info(f"S3 업로드 완료: {url}")
        return url
        
    except Exception as e:
        logger.error(f"S3 업로드 실패: {e}")
        raise HTTPException(status_code=500, detail=f"파일 업로드 실패: {str(e)}")

def validate_image(file: UploadFile) -> bool:
    """이미지 파일 유효성 검사"""
    if not file.content_type or not file.content_type.startswith('image/'):
        return False
    
    # 파일 크기 제한 (10MB)
    if file.size and file.size > 10 * 1024 * 1024:
        return False
    
    return True

# 메인 API 엔드포인트들

@app.post("/api/transfer-hair")
async def transfer_hair_style(
    background_tasks: BackgroundTasks,
    seed_image: UploadFile = File(..., description="시드 이미지"),
    seed_mask: UploadFile = File(..., description="시드 마스크"),
    reference_image: UploadFile = File(..., description="참조 이미지"),
    reference_mask: UploadFile = File(..., description="참조 마스크")
):
    """헤어 스타일 변경 요청 처리"""
    
    # 1. 입력 검증
    files = [seed_image, seed_mask, reference_image, reference_mask]
    file_names = ["seed_image", "seed_mask", "reference_image", "reference_mask"]
    
    for file, name in zip(files, file_names):
        if not validate_image(file):
            raise HTTPException(
                status_code=400, 
                detail=f"{name}이 유효하지 않습니다. 10MB 이하의 이미지 파일만 업로드 가능합니다."
            )
    
    job_id = str(uuid.uuid4())
    
    try:
        # 2. 파일들을 S3에 업로드
        logger.info(f"Job {job_id}: 파일 업로드 시작")
        
        upload_tasks = []
        for file, name in zip(files, file_names):
            content = await file.read()
            key = f"jobs/{job_id}/{name}.png"
            upload_tasks.append(upload_to_s3(content, key, file.content_type))
        
        # 모든 파일 병렬 업로드
        urls = await asyncio.gather(*upload_tasks)
        seed_url, seed_mask_url, ref_url, ref_mask_url = urls
        
        # 3. RunPod 작업 요청 생성
        job_request = {
            "input": {
                "job_id": job_id,
                "seed_image_url": seed_url,
                "seed_mask_url": seed_mask_url,
                "reference_image_url": ref_url,
                "reference_mask_url": ref_mask_url
            }
        }
        
        # 4. Redis에 작업 상태 저장
        job_status = JobStatus(
            job_id=job_id,
            status="PENDING",
            progress="이미지 업로드 완료, AI 처리 대기 중...",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        if redis_client:
            redis_client.setex(
                f"job:{job_id}",
                3600,  # 1시간 만료
                job_status.json()
            )
        
        # 5. 백그라운드에서 RunPod 작업 실행
        background_tasks.add_task(process_runpod_job, job_id, job_request)
        
        logger.info(f"Job {job_id}: 요청 처리 완료")
        
        return JSONResponse({
            "job_id": job_id,
            "status": "PENDING",
            "message": "작업이 시작되었습니다. 상태를 확인하세요.",
            "estimated_time": "30-60초"
        })
        
    except Exception as e:
        logger.error(f"Job {job_id}: 처리 실패 - {e}")
        raise HTTPException(status_code=500, detail=f"작업 처리 실패: {str(e)}")

async def process_runpod_job(job_id: str, job_request: dict):
    """백그라운드에서 RunPod 작업 처리"""
    try:
        # 상태 업데이트: 처리 시작
        if redis_client:
            job_status = JobStatus(
                job_id=job_id,
                status="PROCESSING",
                progress="AI 모델이 이미지를 처리 중입니다...",
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            redis_client.setex(f"job:{job_id}", 3600, job_status.json())
        
        if RUNPOD_ENDPOINT and runpod.api_key:
            # 실제 RunPod 작업 실행
            logger.info(f"Job {job_id}: RunPod 작업 시작")
            
            response = runpod.Endpoint(RUNPOD_ENDPOINT).run(job_request)
            
            # RunPod 작업 상태 폴링
            while True:
                status = runpod.Endpoint(RUNPOD_ENDPOINT).status(response.get('id'))
                
                if status.get('status') == 'COMPLETED':
                    result = status.get('output', {})
                    result_url = result.get('result_url')
                    
                    # 완료 상태 저장
                    if redis_client and result_url:
                        job_status = JobStatus(
                            job_id=job_id,
                            status="COMPLETED", 
                            result_url=result_url,
                            created_at=datetime.now(),
                            updated_at=datetime.now()
                        )
                        redis_client.setex(f"job:{job_id}", 3600, job_status.json())
                    
                    logger.info(f"Job {job_id}: 처리 완료")
                    break
                    
                elif status.get('status') == 'FAILED':
                    error_msg = status.get('error', '알 수 없는 오류')
                    
                    if redis_client:
                        job_status = JobStatus(
                            job_id=job_id,
                            status="FAILED",
                            error=error_msg,
                            created_at=datetime.now(),
                            updated_at=datetime.now()
                        )
                        redis_client.setex(f"job:{job_id}", 3600, job_status.json())
                    
                    logger.error(f"Job {job_id}: RunPod 처리 실패 - {error_msg}")
                    break
                
                # 2초 대기 후 재확인
                await asyncio.sleep(2)
        else:
            # 개발 환경: 모의 처리
            logger.info(f"Job {job_id}: 개발 환경 - 모의 처리")
            await asyncio.sleep(5)  # 5초 대기
            
            # 모의 결과 URL
            mock_result_url = f"https://example.com/results/{job_id}.png"
            
            if redis_client:
                job_status = JobStatus(
                    job_id=job_id,
                    status="COMPLETED",
                    result_url=mock_result_url,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                redis_client.setex(f"job:{job_id}", 3600, job_status.json())
        
    except Exception as e:
        # 에러 상태 저장
        if redis_client:
            job_status = JobStatus(
                job_id=job_id,
                status="FAILED",
                error=str(e),
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            redis_client.setex(f"job:{job_id}", 3600, job_status.json())
        
        logger.error(f"Job {job_id}: 백그라운드 처리 실패 - {e}")

@app.get("/api/job-status/{job_id}")
async def get_job_status(job_id: str):
    """작업 상태 확인"""
    try:
        if not redis_client:
            raise HTTPException(status_code=503, detail="Redis 서비스를 사용할 수 없습니다")
        
        # Redis에서 작업 상태 조회
        job_data = redis_client.get(f"job:{job_id}")
        
        if not job_data:
            raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
        
        job_status = JobStatus.parse_raw(job_data)
        
        return JSONResponse({
            "job_id": job_status.job_id,
            "status": job_status.status,
            "progress": job_status.progress,
            "result_url": job_status.result_url,
            "error": job_status.error,
            "updated_at": job_status.updated_at.isoformat()
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"상태 조회 실패: {e}")
        raise HTTPException(status_code=500, detail="상태 조회 중 오류가 발생했습니다")

@app.get("/api/jobs")
async def list_recent_jobs(limit: int = 10):
    """최근 작업 목록 조회 (관리용)"""
    try:
        if not redis_client:
            return JSONResponse({"jobs": [], "message": "Redis 서비스를 사용할 수 없습니다"})
        
        # Redis에서 작업 키들 조회
        job_keys = redis_client.keys("job:*")
        jobs = []
        
        for key in job_keys[:limit]:
            job_data = redis_client.get(key)
            if job_data:
                try:
                    job_status = JobStatus.parse_raw(job_data)
                    jobs.append({
                        "job_id": job_status.job_id,
                        "status": job_status.status,
                        "created_at": job_status.created_at.isoformat(),
                        "updated_at": job_status.updated_at.isoformat()
                    })
                except:
                    continue
        
        # 최신 순으로 정렬
        jobs.sort(key=lambda x: x["updated_at"], reverse=True)
        
        return JSONResponse({"jobs": jobs})
        
    except Exception as e:
        logger.error(f"작업 목록 조회 실패: {e}")
        return JSONResponse({"jobs": [], "error": str(e)})

@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    """작업 삭제 (관리용)"""
    try:
        if not redis_client:
            raise HTTPException(status_code=503, detail="Redis 서비스를 사용할 수 없습니다")
        
        deleted = redis_client.delete(f"job:{job_id}")
        
        if deleted:
            return JSONResponse({"message": f"작업 {job_id}가 삭제되었습니다"})
        else:
            raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"작업 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail="작업 삭제 중 오류가 발생했습니다")

# 예외 처리
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Global exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "내부 서버 오류가 발생했습니다"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        log_level="info"
    )
