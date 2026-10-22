#!/bin/sh
# Dump the production database to $BACKUP_DIR (default ~/mascot-backups) and
# keep the newest 7 dumps. Schedule it with cron, for example daily at 03:00:
#   0 3 * * * /home/opc/Mascot/deploy/backup.sh >> /home/opc/mascot-backups/backup.log 2>&1
# Restore: docker compose -f deploy/docker-compose.prod.yml exec -T db \
#   sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' < <dump file>
set -eu

cd "$(dirname "$0")"
backup_dir="${BACKUP_DIR:-$HOME/mascot-backups}"
mkdir -p "$backup_dir"
target="$backup_dir/mascot-$(date +%Y%m%d-%H%M%S).dump"

docker compose -f docker-compose.prod.yml exec -T db \
  sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$target.partial"
mv "$target.partial" "$target"

ls -1t "$backup_dir"/mascot-*.dump | tail -n +8 | xargs -r rm --
echo "backup written: $target"
