#!/bin/bash
echo "필요한 패키지 설치 중..."

# Python 가상환경 생성
python3 -m venv venv
source venv/bin/activate

# 라이브러리 설치
pip install -r requirements.txt

# .env 파일 생성 (보안상 GitHub에는 올리지 않음)
cat > .env << 'EOF'
GEMINI_API_KEY=AIzaSyAbF6-puUPZqx7vpDvb_XNrDj3-a_e0ja4
AWS_ACCESS_KEY=AKIAQXUIYAFFQ2RRHFNH
AWS_SECRET_KEY=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
EOF

echo "설치 완료!"
