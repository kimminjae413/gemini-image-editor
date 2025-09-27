#!/bin/bash
# SSH 서버 설정 스크립트

echo "🔧 SSH 테스트 환경 설정 시작..."

# 1. SSH 서버 설치 (Ubuntu/Debian)
sudo apt update
sudo apt install -y openssh-server

# 2. SSH 서비스 시작
sudo systemctl start ssh
sudo systemctl enable ssh

# 3. 테스터 계정 생성
sudo adduser vmodel-tester --gecos "" --disabled-password
echo "vmodel-tester:TestPassword123!" | sudo chpasswd

# 4. 테스터 권한 설정
sudo usermod -aG sudo vmodel-tester

# 5. 작업 디렉토리 설정
sudo mkdir -p /home/vmodel-tester/vmodel-test
sudo cp -r * /home/vmodel-tester/vmodel-test/
sudo chown -R vmodel-tester:vmodel-tester /home/vmodel-tester/vmodel-test

# 6. Python 환경 설정
sudo -u vmodel-tester pip install -r requirements.txt

echo "✅ SSH 테스트 환경 구축 완료!"
echo "📋 테스터 접속 정보:"
echo "   SSH 명령어: ssh vmodel-tester@$(hostname -I | awk '{print $1}')"
echo "   계정: vmodel-tester"
echo "   비밀번호: TestPassword123!"
echo "   작업 폴더: /home/vmodel-tester/vmodel-test"
