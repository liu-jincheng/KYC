#!/bin/bash
set -e

SERVER="root@115.190.197.29"
REMOTE_DIR="/srv/kyc/KYC"

# ========== 发布前自动备份 ==========
echo "🔐 发布前备份数据库..."
ssh ${SERVER} "
  if [ -f ${REMOTE_DIR}/data/crm.db ]; then
    APP_DIR=${REMOTE_DIR} bash ${REMOTE_DIR}/scripts/backup_db.sh
  else
    echo '⚠️ 远程数据库不存在（首次部署），跳过备份'
  fi
"

echo "📦 同步项目文件到服务器..."
rsync -avz --delete \
  --exclude '.git' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude 'venv' \
  --exclude '.cursor' \
  --exclude 'data/' \
  --exclude 'backups/' \
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

  sleep 2
  echo "✅ 部署完成"
EOF

echo "🌐 访问 http://115.190.197.29 验证"
echo ""
echo "💡 如需回滚数据库: ssh ${SERVER} 'APP_DIR=${REMOTE_DIR} ${REMOTE_DIR}/scripts/restore_db.sh --latest'"
