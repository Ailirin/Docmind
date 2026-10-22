#!/bin/sh
# Entrypoint: исправляет права на примонтированный volume, затем запускает процесс
# от имени appuser. Запускается как root, до USER-инструкции.
set -e

# Примонтированный volume создаётся Docker'ом от root;
# даём право на запись нашему appuser.
chown -R appuser:appgroup /app/uploads 2>/dev/null || true

# Передаём управление команде (CMD) от имени appuser.
exec gosu appuser "$@"
