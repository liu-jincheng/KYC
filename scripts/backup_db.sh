#!/bin/bash
# ============================================================
# SQLite 数据库定时备份脚本
# 功能: 在线安全备份、完整性校验、gzip 压缩、滚动保留
# 用法: ./scripts/backup_db.sh [--offsite]
# ============================================================
set -euo pipefail

# --------------- 可配置参数 ---------------
APP_DIR="${APP_DIR:-/srv/kyc/KYC}"
DB_FILE="${APP_DIR}/data/crm.db"
BACKUP_DIR="${APP_DIR}/backups"
BACKUP_LOG="${BACKUP_DIR}/backup.log"

RETAIN_COUNT="${RETAIN_COUNT:-60}"        # 保留最近 60 份（12h 频率约 30 天）
OFFSITE_ENABLED="${OFFSITE_ENABLED:-0}"   # 1 = 启用异地推送
OFFSITE_TARGET="${OFFSITE_TARGET:-}"      # rsync 目标, 如 user@host:/path/backups/

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_NAME="crm_${TIMESTAMP}.db"
BACKUP_GZ="${BACKUP_NAME}.gz"

# --------------- 工具函数 ---------------
log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg"
    echo "$msg" >> "$BACKUP_LOG"
}

die() {
    log "ERROR: $*"
    exit 1
}

# --------------- 预检 ---------------
mkdir -p "$BACKUP_DIR"
[ -f "$DB_FILE" ] || die "数据库文件不存在: $DB_FILE"
command -v sqlite3 >/dev/null 2>&1 || die "sqlite3 未安装"

log "===== 开始备份 ====="

# --------------- 1. 在线安全备份（使用 SQLite .backup API）---------------
TEMP_BACKUP="${BACKUP_DIR}/${BACKUP_NAME}"
sqlite3 "$DB_FILE" ".backup '${TEMP_BACKUP}'" || die "sqlite3 .backup 失败"
log "备份文件已生成: ${TEMP_BACKUP}"

# --------------- 2. 完整性校验 ---------------
INTEGRITY=$(sqlite3 "$TEMP_BACKUP" "PRAGMA integrity_check;" 2>&1)
if [ "$INTEGRITY" != "ok" ]; then
    rm -f "$TEMP_BACKUP"
    die "完整性校验失败: $INTEGRITY"
fi
log "完整性校验通过"

ROW_COUNT=$(sqlite3 "$TEMP_BACKUP" "SELECT COUNT(*) FROM customers;" 2>/dev/null || echo "N/A")
log "客户记录数: ${ROW_COUNT}"

# --------------- 3. 压缩 ---------------
gzip -f "$TEMP_BACKUP" || die "gzip 压缩失败"
COMPRESSED="${BACKUP_DIR}/${BACKUP_GZ}"
FILESIZE=$(du -h "$COMPRESSED" | cut -f1)
log "压缩完成: ${COMPRESSED} (${FILESIZE})"

# --------------- 4. 滚动保留（删除最老的，保留最新 RETAIN_COUNT 份）---------------
TOTAL=$(ls -1 "${BACKUP_DIR}"/crm_*.db.gz 2>/dev/null | wc -l | tr -d ' ')
if [ "$TOTAL" -gt "$RETAIN_COUNT" ]; then
    DELETE_COUNT=$((TOTAL - RETAIN_COUNT))
    ls -1t "${BACKUP_DIR}"/crm_*.db.gz | tail -n "$DELETE_COUNT" | xargs rm -f
    log "已清理 ${DELETE_COUNT} 份过期备份，当前保留 ${RETAIN_COUNT} 份"
else
    log "当前共 ${TOTAL} 份备份，保留阈值 ${RETAIN_COUNT}，无需清理"
fi

# --------------- 5. 异地推送（可选）---------------
if [ "$OFFSITE_ENABLED" = "1" ] && [ -n "$OFFSITE_TARGET" ]; then
    log "推送到异地: ${OFFSITE_TARGET}"
    if rsync -az "$COMPRESSED" "$OFFSITE_TARGET"; then
        log "异地推送成功"
    else
        log "WARNING: 异地推送失败（备份本身已完成）"
    fi
fi

log "===== 备份完成 ====="
