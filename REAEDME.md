# 💇‍♀️ AI 헤어스타일 변경 서비스 MVP

참조 이미지 기반으로 헤어스타일을 변경하는 AI 웹 서비스입니다. 최소 비용으로 빠르게 시작할 수 있는 MVP 버전입니다.

## 🎯 주요 기능

- **AI 헤어스타일 변경**: VModel AI를 활용한 자연스러운 헤어스타일 변환
- **다중 시드 관리**: 여러 개의 얼굴 이미지를 저장하고 관리
- **실시간 처리**: 30-60초 내 빠른 변환 결과 제공
- **처리 기록**: 이전 변환 결과를 저장하고 재다운로드 가능
- **직관적 UI**: Streamlit 기반의 사용하기 쉬운 웹 인터페이스

## 🏗️ 아키텍처

```
[Frontend - Streamlit] ↔ [Backend - FastAPI] ↔ [VModel AI API]
                                ↓
                         [SQLite Database]
```

## 🚀 빠른 시작

### 1. 프로젝트 클론 및 설정

```bash
# 프로젝트 디렉토리 생성
mkdir hair-style-ai
cd hair-style-ai

# 파일들 생성 (위의 artifacts 내용을 각각 저장)
# main.py, app.py, requirements.txt, start.sh, .env.example
```

### 2. 환경 설정

```bash
# 가상환경 생성
python -m venv venv

# 가상환경 활성화
# Linux/Mac:
source venv/bin/activate
# Windows:
# venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 3. API 키 설정

```bash
# .env 파일 생성
cp .env.example .env

# VModel API 키 설정 (https://vmodel.ai에서 발급)
export VMODEL_API_KEY="your-vmodel-api-key-here"
```

### 4. 서비스 실행

#### 방법 1: 자동 스크립트 사용
```bash
chmod +x start.sh
./start.sh
```

#### 방법 2: 수동 실행
```bash
# 터미널 1: 백엔드 서버
python main.py

# 터미널 2: 프론트엔드
streamlit run app.py
```

### 5. 서비스 접속

- **웹 인터페이스**: http://localhost:8501
- **API 문서**: http://localhost:8000/docs
- **헬스체크**: http://localhost:8000/health

## 📖 사용 방법

### 1. 시드 이미지 업로드
- 얼굴이 명확히 보이는 정면 사진 업로드
- PNG, JPEG 형식 지원 (최대 10MB)

### 2. 헤어스타일 변경
- 업로드된 시드 이미지 선택
- 원하는 헤어스타일의 참조 이미지 업로드
- AI 변환 실행 (30-60초 소요)

### 3. 결과 확인 및 다운로드
- 변환 결과 이미지 확인
- PNG 형식으로 다운로드

## 💰 비용 분석

### MVP 단계 비용 (월 1000건 기준)
- **VModel API**: $15-55
- **서버 호스팅**: $0-5 (로컬) / $10-30 (클라우드)
- **총 비용**: $15-85

### 사용량별 예상 비용
| 월 사용량 | API 비용 | 서버 비용 | 총 비용 |
|-----------|----------|-----------|---------|
| 100건     | $2-6     | $5        | $7-11   |
| 1,000건   | $15-55   | $10       | $25-65  |
| 10,000건  | $150-550 | $50       | $200-600|

## 🔧 API 엔드포인트

### 시드 이미지 관리
- `POST /upload-seed/` - 시드 이미지 업로드
- `GET /seeds/{user_id}` - 사용자 시드 목록
- `GET /seed-image/{seed_id}` - 시드 이미지 조회

### 헤어스타일 변경
- `POST /transfer-hair/` - 헤어 변경 처리
- `GET /result/{process_id}` - 결과 이미지 조회

### 기록 관리
- `GET /history/{user_id}` - 처리 기록 조회

## 🔍 트러블슈팅

### 자주 발생하는 문제

1. **API 키 오류**
   ```bash
   # 환경변수 확인
   echo $VMODEL_API_KEY
   
   # 없다면 설정
   export VMODEL_API_KEY="your-key"
   ```

2. **포트 충돌**
   ```bash
   # 포트 사용 확인
   lsof -i :8000
   lsof -i :8501
   
   # 프로세스 종료
   kill -9 <PID>
   ```

3. **의존성 오류**
   ```bash
   # 가상환경 재생성
   rm -rf venv
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **이미지 처리 오류**
   - 이미지 크기: 10MB 이하
   - 지원 형식: PNG, JPEG
   - 권장 해상도: 512x512 이상

## 📈 확장 계획

### 2단계: 성장 단계 (+1주)
- RunPod Serverless로 자체 GPU 인프라 도입
- 비용 최적화: 월 1000건 기준 $25
- 처리 품질 개선 (85% → 90%)

### 3단계: 스케일 단계 (+2주)
- Stable-Hair 모델 직접 구현
- 대량 처리 최적화
- 최고 품질 (90% → 95%)

## 🛠️ 개발 환경

### 필요 도구
- Python 3.8+
- pip (package manager)
- VModel AI API 키

### 추천 IDE 설정
```json
// VS Code settings.json
{
    "python.defaultInterpreterPath": "./venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.formatting.provider": "black"
}
```

## 🔒 보안 고려사항

1. **API 키 보안**
   - 환경변수 사용
   - .env 파일을 git에서 제외

2. **이미지 데이터**
   - 로컬 SQLite에 저장
   - 정기적인 데이터 정리 필요

3. **사용량 제한**
   - Rate limiting 구현 권장
   - 사용자별 할당량 관리

## 📝 라이센스

MIT License - 상업적 이용 가능

## 🤝 기여하기

1. Fork the project
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

## 📞 지원

- 이슈 리포트: GitHub Issues
- 기술 문의: [이메일 주소]
- 문서: [문서 링크]

## 🎉 성공 사례

MVP 검증 후 실제 사용자 피드백을 바탕으로 지속적인 개선을 진행하세요:

1. **초기 목표**: 지인 10명 테스트
2. **1차 목표**: 온라인 사용자 100명
3. **2차 목표**: 월 1000건 처리
4. **최종 목표**: 수익성 확보

---

💡 **빠른 런칭이 핵심입니다!** 완벽함보다는 사용자 피드백을 빠르게 받아 개선해나가세요.
