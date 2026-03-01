#!/bin/bash
set -e

SERVER="root@115.190.197.29"
REMOTE_DIR="/srv/kyc/KYC"

echo "📦 同步项目文件到服务器..."
rsync -avz --delete \
  --exclude '.git' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude 'venv' \
  --exclude '.cursor' \
  /Users/kim6/Projects/KYC/ \
  ${SERVER}:${REMOTE_DIR}/

echo "🔄 安装依赖并重启服务..."
ssh ${SERVER} << 'EOF'
  cd /srv/kyc/KYC

  [ ! -d "venv" ] && python3 -m venv venv

  source venv/bin/activate
  pip install -r requirements.txt -q

  if systemctl is-enabled kyc &>/dev/null; then
    systemctl restart kyc
  else
    pkill -f "uvicorn app.main:app" || true
    nohup venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 > /tmp/kyc.log 2>&1 &
  fi
ssh root@115.190.197.29 "cat /etc/systemd/system/kyc.service"
  sleep 2
  echo "✅ 部署完成"
EOF

echo "🌐 访问 http://115.190.197.29 验证"