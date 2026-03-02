#!/bin/bash
# ============================================================
# 在服务器上配置数据库定时备份 cron 任务
# 用法: 在服务器上执行  bash /srv/kyc/KYC/scripts/setup_cron.sh
# ============================================================
set -euo pipefail

APP_DIR="${APP_DIR:-/srv/kyc/KYC}"
BACKUP_SCRIPT="${APP_DIR}/scripts/backup_db.sh"
CRON_SCHEDULE="${CRON_SCHEDULE:-0 */12 * * *}"   # 默认每 12 小时
CRON_TAG="# kyc-db-backup"

if [ ! -f "$BACKUP_SCRIPT" ]; then
    echo "错误: 备份脚本不存在: $BACKUP_SCRIPT"
    exit 1
fi

chmod +x "$BACKUP_SCRIPT"

CRON_LINE="${CRON_SCHEDULE} APP_DIR=${APP_DIR} ${BACKUP_SCRIPT} >> ${APP_DIR}/backups/cron.log 2>&1 ${CRON_TAG}"

EXISTING=$(crontab -l 2>/dev/null || true)

if echo "$EXISTING" | grep -qF "$CRON_TAG"; then
    echo "更新已有 cron 任务..."
    NEW_CRON=$(echo "$EXISTING" | grep -vF "$CRON_TAG")
    echo "${NEW_CRON}"$'\n'"${CRON_LINE}" | crontab -
else
    echo "新增 cron 任务..."
    echo "${EXISTING}"$'\n'"${CRON_LINE}" | crontab -
fi

echo "当前 cron 任务:"
crontab -l | grep -F "$CRON_TAG" || true
echo ""
echo "已配置: ${CRON_SCHEDULE} 自动执行备份"
echo "日志位置: ${APP_DIR}/backups/cron.log"
