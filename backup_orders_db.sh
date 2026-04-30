#!/bin/bash

set -e

DB_FILE="/opt/order-app/orders.db"
BASE_BACKUP_DIR="/opt/backups/order-app"

DAILY_DIR="$BASE_BACKUP_DIR/daily"
MONTHLY_DIR="$BASE_BACKUP_DIR/monthly"
YEARLY_DIR="$BASE_BACKUP_DIR/yearly"

TODAY=$(date +"%F")
YEAR_MONTH=$(date +"%Y-%m")
YEAR_ONLY=$(date +"%Y")

mkdir -p "$DAILY_DIR" "$MONTHLY_DIR" "$YEARLY_DIR"

if [ ! -f "$DB_FILE" ]; then
    echo "Database file not found: $DB_FILE"
    exit 1
fi

# 1. 每天备份
cp "$DB_FILE" "$DAILY_DIR/orders_daily_$TODAY.db"
echo "Daily backup created: $DAILY_DIR/orders_daily_$TODAY.db"

# 2. 如果是每月1号，生成月备份
DAY_OF_MONTH=$(date +"%d")
if [ "$DAY_OF_MONTH" = "01" ]; then
    cp "$DB_FILE" "$MONTHLY_DIR/orders_monthly_$YEAR_MONTH.db"
    echo "Monthly backup created: $MONTHLY_DIR/orders_monthly_$YEAR_MONTH.db"
fi

# 3. 如果是1月1号，生成年备份
MONTH_DAY=$(date +"%m-%d")
if [ "$MONTH_DAY" = "01-01" ]; then
    cp "$DB_FILE" "$YEARLY_DIR/orders_yearly_$YEAR_ONLY.db"
    echo "Yearly backup created: $YEARLY_DIR/orders_yearly_$YEAR_ONLY.db"
fi

# 4. 删除14天前的日备份
find "$DAILY_DIR" -type f -name "orders_daily_*.db" -mtime +14 -delete

echo "Backup job done."