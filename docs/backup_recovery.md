# 数据库备份与恢复手册

## 概述

| 项目 | 说明 |
|------|------|
| 数据库 | SQLite (`data/crm.db`) |
| RPO 目标 | <= 12 小时（每 12 小时自动备份） |
| RTO 目标 | <= 2 小时（手动恢复） |
| 备份保留 | 最近 60 份（约 30 天） |
| 备份位置 | `backups/crm_YYYYMMDD_HHMMSS.db.gz` |

## 1. 自动备份

### 1.1 备份脚本能力

`scripts/backup_db.sh` 执行以下步骤：

1. 使用 SQLite `.backup` API 在线安全复制（不锁表）
2. `PRAGMA integrity_check` 完整性校验
3. gzip 压缩
4. 滚动保留（超过 `RETAIN_COUNT` 份自动清理最旧的）
5. 可选异地推送（通过 rsync）

### 1.2 配置定时备份（二选一）

**方式一：cron（推荐）**

在服务器上执行：

```bash
bash /srv/kyc/KYC/scripts/setup_cron.sh
```

验证：

```bash
crontab -l | grep kyc-db-backup
```

自定义频率（如每 6 小时）：

```bash
CRON_SCHEDULE="0 */6 * * *" bash /srv/kyc/KYC/scripts/setup_cron.sh
```

**方式二：systemd timer**

```bash
cp /srv/kyc/KYC/scripts/kyc-backup.service /etc/systemd/system/
cp /srv/kyc/KYC/scripts/kyc-backup.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now kyc-backup.timer
systemctl list-timers | grep kyc
```

### 1.3 手动触发备份

```bash
APP_DIR=/srv/kyc/KYC /srv/kyc/KYC/scripts/backup_db.sh
```

### 1.4 查看备份日志

```bash
tail -50 /srv/kyc/KYC/backups/backup.log
```

## 2. 异地副本

### 2.1 从开发机拉取服务器备份

```bash
./scripts/offsite_sync.sh
```

默认存储到 `~/kyc-offsite-backups/`，可通过 `LOCAL_BACKUP_DIR` 自定义。

### 2.2 启用备份时自动推送

编辑 cron 或在脚本调用时设置环境变量：

```bash
OFFSITE_ENABLED=1 OFFSITE_TARGET=user@backup-host:/data/kyc-backups/ \
  APP_DIR=/srv/kyc/KYC /srv/kyc/KYC/scripts/backup_db.sh
```

## 3. 灾难恢复

### 3.1 恢复到最新备份

```bash
APP_DIR=/srv/kyc/KYC /srv/kyc/KYC/scripts/restore_db.sh --latest
```

### 3.2 恢复到指定备份

```bash
APP_DIR=/srv/kyc/KYC /srv/kyc/KYC/scripts/restore_db.sh crm_20260302_120000.db.gz
```

### 3.3 交互式选择

```bash
APP_DIR=/srv/kyc/KYC /srv/kyc/KYC/scripts/restore_db.sh
```

会列出所有可用备份，输入编号即可。

### 3.4 干跑校验（不执行实际恢复）

```bash
APP_DIR=/srv/kyc/KYC /srv/kyc/KYC/scripts/restore_db.sh --dry-run --latest
```

### 3.5 恢复流程说明

恢复脚本自动执行以下步骤：

1. 解压备份到临时目录
2. `PRAGMA integrity_check` 校验
3. 显示备份与当前数据库的记录数对比
4. 要求输入 `YES` 确认
5. 将当前数据库保存为 `crm_pre_restore_*.db`（回滚保护）
6. 停止 KYC 服务（如有 systemd）
7. 替换数据库文件
8. 恢复后再次校验
9. 重启服务

### 3.6 回滚

如恢复后发现问题，用恢复前保存的快照回滚：

```bash
cp /srv/kyc/KYC/backups/crm_pre_restore_XXXXXXXX_XXXXXX.db /srv/kyc/KYC/data/crm.db
systemctl restart kyc
```

## 4. 恢复演练检查清单

建议每月执行一次，记录结果：

- [ ] 从备份目录选取一份备份
- [ ] 在测试环境解压并校验完整性
- [ ] 确认客户记录数与预期一致
- [ ] 用恢复后的数据库启动应用，验证页面可正常访问
- [ ] 记录恢复耗时（目标 < 2 小时）
- [ ] 将演练结果记录到运维日志

## 5. 环境变量速查

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `APP_DIR` | `/srv/kyc/KYC` | 应用根目录 |
| `RETAIN_COUNT` | `60` | 备份保留份数 |
| `OFFSITE_ENABLED` | `0` | 是否启用异地推送 |
| `OFFSITE_TARGET` | (空) | rsync 异地目标 |
| `CRON_SCHEDULE` | `0 */12 * * *` | cron 备份频率 |
| `SERVER` | `root@115.190.197.29` | 异地同步时的服务器地址 |
| `LOCAL_BACKUP_DIR` | `~/kyc-offsite-backups` | 本地异地备份目录 |
