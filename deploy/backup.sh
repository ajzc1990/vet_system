#!/bin/bash
# Backup diario de VeterSystem: base de datos + archivos multimedia (estudios,
# logos). Pensado para correr por cron en el VPS, no a mano.
#
# Instalación (una sola vez, en el VPS):
#   chmod +x /var/www/vet_system_new/deploy/backup.sh
#   crontab -e
#   # agregar la línea:
#   0 3 * * * /var/www/vet_system_new/deploy/backup.sh >> /var/log/vetersystem_backup.log 2>&1
#
# Restaurar un backup de base de datos:
#   gunzip -c /root/backups/vetersystem/db_AAAAMMDD_HHMMSS.sql.gz | \
#     docker compose exec -T db psql -U "$POSTGRES_USER" "$POSTGRES_DB"
#
# Restaurar los archivos multimedia:
#   docker run --rm -v vet_system_media_volume:/media_dst \
#     -v /root/backups/vetersystem:/backup_src \
#     alpine sh -c "cd /media_dst && tar -xzf /backup_src/media_AAAAMMDD_HHMMSS.tar.gz"

set -euo pipefail

PROYECTO_DIR="/var/www/vet_system_new"
DESTINO="/root/backups/vetersystem"
RETENCION_DIAS=14
FECHA="$(date +%Y%m%d_%H%M%S)"

mkdir -p "$DESTINO"
cd "$PROYECTO_DIR"

# 1. Dump de la base de datos (usa las credenciales ya cargadas en el contenedor,
#    no las lee de .env, así nunca queda desactualizado si cambian).
docker compose exec -T db bash -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  | gzip > "$DESTINO/db_${FECHA}.sql.gz"

# 2. Archivos multimedia (estudios médicos, logos de veterinarias, etc.)
docker run --rm \
  -v vet_system_media_volume:/media_src:ro \
  -v "$DESTINO":/backup_dst \
  alpine tar -czf "/backup_dst/media_${FECHA}.tar.gz" -C /media_src .

# 3. Limpieza: borra backups más viejos que RETENCION_DIAS
find "$DESTINO" -name "db_*.sql.gz" -mtime +"$RETENCION_DIAS" -delete
find "$DESTINO" -name "media_*.tar.gz" -mtime +"$RETENCION_DIAS" -delete

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Backup OK: db_${FECHA}.sql.gz y media_${FECHA}.tar.gz"
