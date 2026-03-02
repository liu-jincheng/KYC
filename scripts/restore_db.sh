#!/bin/bash
# ============================================================
# SQLite 数据库恢复脚本
# 从备份文件恢复 crm.db，包含安全检查与回滚保护
#
# 用法:
#   ./scripts/restore_db.sh                          # 交互选择备份
#   ./scripts/restore_db.sh crm_20260302_120000.db.gz  # 指定备份文件
#   ./scripts/restore_db.sh --latest                 # 恢复到最新备份
#   ./scripts/restore_db.sh --dry-run --latest       # 仅校验不执行
# ============================================================
set -euo pipefail

APP_DIR="${APP_DIR:-/srv/kyc/KYC}"
DB_FILE="${APP_DIR}/data/crm.db"
BACKUP_DIR="${APP_DIR}/backups"

DRY_RUN=0
TARGET_BACKUP=""

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

die() {
    log "ERROR: $*"
    exit 1
}

# --------------- 解析参数 ---------------
while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run)  DRY_RUN=1; shift ;;
        --latest)   TARGET_BACKUP="__latest__"; shift ;;
        *)          TARGET_BACKUP="$1"; shift ;;
    esac
done

# --------------- 查找备份文件 ---------------
AVAILABLE=$(ls -1t "${BACKUP_DIR}"/crm_*.db.gz 2>/dev/null || true)
if [ -z "$AVAILABLE" ]; then
    die "未找到可用备份 (${BACKUP_DIR}/crm_*.db.gz)"
fi

if [ "$TARGET_BACKUP" = "__latest__" ]; then
    RESTORE_FILE=$(echo "$AVAILABLE" | head -1)
elif [ -n "$TARGET_BACKUP" ]; then
    if [ -f "$TARGET_BACKUP" ]; then
        RESTORE_FILE="$TARGET_BACKUP"
    elif [ -f "${BACKUP_DIR}/${TARGET_BACKUP}" ]; then
        RESTORE_FILE="${BACKUP_DIR}/${TARGET_BACKUP}"
    else
        die "指定的备份文件不存在: $TARGET_BACKUP"
    fi
else
    log "可用备份列表:"
    echo "$AVAILABLE" | nl -ba
    echo ""
    read -rp "请输入要恢复的编号 (1 = 最新): " CHOICE
    RESTORE_FILE=$(echo "$AVAILABLE" | sed -n "${CHOICE}p")
    [ -z "$RESTORE_FILE" ] && die "无效选择"
fi

log "选定备份: $(basename "$RESTORE_FILE")"
log "备份大小: $(du -h "$RESTORE_FILE" | cut -f1)"

# --------------- 解压到临时文件并校验 ---------------
TEMP_DIR=$(mktemp -d)
TEMP_DB="${TEMP_DIR}/restore_candidate.db"
trap 'rm -rf "$TEMP_DIR"' EXIT

log "解压备份中..."
gunzip -c "$RESTORE_FILE" > "$TEMP_DB" || die "解压失败"

log "校验备份完整性..."
INTEGRITY=$(sqlite3 "$TEMP_DB" "PRAGMA integrity_check;" 2>&1)
if [ "$INTEGRITY" != "ok" ]; then
    die "备份文件完整性校验失败: $INTEGRITY"
fi

ROW_COUNT=$(sqlite3 "$TEMP_DB" "SELECT COUNT(*) FROM customers;" 2>/dev/null || echo "N/A")
TABLE_COUNT=$(sqlite3 "$TEMP_DB" "SELECT COUNT(*) FROM sqlite_master WHERE type='table';" 2>/dev/null || echo "N/A")
log "校验通过 — 客户记录: ${ROW_COUNT}, 数据表: ${TABLE_COUNT}"

if [ "$DRY_RUN" = "1" ]; then
    log "[DRY-RUN] 校验完成，未执行实际恢复"
    exit 0
fi

# --------------- 安全确认 ---------------
if [ -f "$DB_FILE" ]; then
    CURRENT_ROWS=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM customers;" 2>/dev/null || echo "N/A")
    log "当前数据库客户记录: ${CURRENT_ROWS}"
fi

echo ""
echo "========================================"
echo "  即将用备份覆盖当前数据库"
echo "  备份文件: $(basename "$RESTORE_FILE")"
echo "  备份记录数: ${ROW_COUNT}"
echo "  当前记录数: ${CURRENT_ROWS:-N/A}"
echo "========================================"
read -rp "确认恢复? (输入 YES 继续): " CONFIRM
if [ "$CONFIRM" != "YES" ]; then
    log "用户取消恢复"
    exit 0
fi

# --------------- 备份当前数据库（恢复前保护）---------------
if [ -f "$DB_FILE" ]; then
    PRE_RESTORE_BACKUP="${BACKUP_DIR}/crm_pre_restore_$(date +%Y%m%d_%H%M%S).db"
    cp "$DB_FILE" "$PRE_RESTORE_BACKUP"
    log "已保存恢复前快照: ${PRE_RESTORE_BACKUP}"
fi

# --------------- 执行恢复 ---------------
log "停止应用（如果有 systemd 服务）..."
if systemctl is-active kyc &>/dev/null; then
    systemctl stop kyc
    RESTART_SERVICE=1
else
    RESTART_SERVICE=0
fi

cp "$TEMP_DB" "$DB_FILE" || die "复制数据库文件失败"
log "数据库已恢复"

VERIFY=$(sqlite3 "$DB_FILE" "PRAGMA integrity_check;" 2>&1)
if [ "$VERIFY" != "ok" ]; then
    die "恢复后校验失败，请从 ${PRE_RESTORE_BACKUP:-手动} 回滚"
fi

if [ "$RESTART_SERVICE" = "1" ]; then
    systemctl start kyc
    log "应用已重启"
fi

log "===== 恢复完成 ====="
log "恢复来源: $(basename "$RESTORE_FILE")"
log "客户记录: ${ROW_COUNT}"
