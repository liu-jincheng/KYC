#!/bin/bash
# ============================================================
# 异地备份同步脚本
# 将服务器上的备份副本拉取到本地或推送到第三方存储
#
# 方式一（从开发机拉取服务器备份）:
#   SYNC_MODE=pull ./scripts/offsite_sync.sh
#
# 方式二（在服务器上推送到远端）:
#   SYNC_MODE=push OFFSITE_TARGET=user@backup-host:/data/kyc-backups/ ./scripts/offsite_sync.sh
# ============================================================
set -euo pipefail

SYNC_MODE="${SYNC_MODE:-pull}"
SERVER="${SERVER:-root@115.190.197.29}"
REMOTE_BACKUP_DIR="${REMOTE_BACKUP_DIR:-/srv/kyc/KYC/backups}"
LOCAL_BACKUP_DIR="${LOCAL_BACKUP_DIR:-$HOME/kyc-offsite-backups}"
OFFSITE_TARGET="${OFFSITE_TARGET:-}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

if [ "$SYNC_MODE" = "pull" ]; then
    # 从服务器拉取备份到本地
    mkdir -p "$LOCAL_BACKUP_DIR"
    log "拉取模式: ${SERVER}:${REMOTE_BACKUP_DIR}/ -> ${LOCAL_BACKUP_DIR}/"

    rsync -avz --include='crm_*.db.gz' --include='backup.log' --exclude='*' \
        "${SERVER}:${REMOTE_BACKUP_DIR}/" \
        "${LOCAL_BACKUP_DIR}/"

    SYNCED=$(ls -1 "${LOCAL_BACKUP_DIR}"/crm_*.db.gz 2>/dev/null | wc -l | tr -d ' ')
    log "同步完成，本地共 ${SYNCED} 份备份副本"
    log "存储位置: ${LOCAL_BACKUP_DIR}/"

    LATEST=$(ls -1t "${LOCAL_BACKUP_DIR}"/crm_*.db.gz 2>/dev/null | head -1)
    if [ -n "$LATEST" ]; then
        log "最新备份: $(basename "$LATEST") ($(du -h "$LATEST" | cut -f1))"
    fi

elif [ "$SYNC_MODE" = "push" ]; then
    # 从服务器推送到异地目标
    if [ -z "$OFFSITE_TARGET" ]; then
        log "ERROR: push 模式需要设置 OFFSITE_TARGET"
        exit 1
    fi

    APP_DIR="${APP_DIR:-/srv/kyc/KYC}"
    BACKUP_DIR="${APP_DIR}/backups"
    log "推送模式: ${BACKUP_DIR}/ -> ${OFFSITE_TARGET}"

    rsync -avz --include='crm_*.db.gz' --exclude='*' \
        "${BACKUP_DIR}/" \
        "${OFFSITE_TARGET}"

    log "推送完成"
else
    log "ERROR: 未知 SYNC_MODE=${SYNC_MODE}，支持 pull / push"
    exit 1
fi
