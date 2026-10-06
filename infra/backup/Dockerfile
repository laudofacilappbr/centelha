# Backup diário (#26): PostgreSQL e volume de áudio para um bucket S3 (R2 ou B2),
# cifrados pelo rclone antes de sair da VPS. Um container só para isso (ADR 0001).
FROM alpine:3.21
RUN apk add --no-cache bash postgresql17-client rclone tzdata
COPY backup.sh restaurar.sh agendar.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/*.sh
CMD ["agendar.sh"]
