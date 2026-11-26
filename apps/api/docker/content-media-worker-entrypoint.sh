#!/bin/sh
set -eu

normalize_bool() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

CONTENT_MEDIA="$(normalize_bool "${ALLPHA_CONTENT_MEDIA_WORKER_ENABLED:-false}")"
CONTENT_TRANSCODE="$(normalize_bool "${ALLPHA_CONTENT_TRANSCODE_WORKER_ENABLED:-false}")"
CONTENT_CALLBACK="$(normalize_bool "${ALLPHA_CONTENT_PROVIDER_CALLBACK_WORKER_ENABLED:-false}")"
CONTENT_CLEANUP="$(normalize_bool "${ALLPHA_CONTENT_PROVIDER_CLEANUP_WORKER_ENABLED:-false}")"
MEDIA_ENABLED=false

for value in "$CONTENT_MEDIA" "$CONTENT_TRANSCODE" "$CONTENT_CALLBACK" "$CONTENT_CLEANUP"; do
  case "$value" in
    true) MEDIA_ENABLED=true ;;
    false) ;;
    *) echo "Content media worker flags must be true or false" >&2; exit 1 ;;
  esac
done

if [ "$MEDIA_ENABLED" != "true" ]; then
  echo "Dedicated content media worker disabled; scanner bootstrap and job claims are skipped"
  exec sleep infinity
fi

if [ "$(normalize_bool "${ALLPHA_CLAMAV_ENABLED:-false}")" != "true" ] ||
   [ "$(normalize_bool "${ALLPHA_DOCUMENT_SCANNER_MODE:-}")" != "clamd" ]; then
  echo "Content media worker requires explicitly enabled pinned ClamAV scanning" >&2
  exit 1
fi

if [ "${ALLPHA_DOCUMENT_SCANNER_ID:-}" != "clamav-local" ] ||
   [ -z "${ALLPHA_DOCUMENT_SCANNER_ENGINE_VERSION:-}" ] ||
   [ -z "${ALLPHA_DOCUMENT_SCANNER_SIGNATURE_VERSION:-}" ]; then
  echo "Content media worker requires scanner ID and exact engine/signature deployment pins" >&2
  exit 1
fi

mkdir -p /run/clamav
chown clamav:clamav /run/clamav /var/lib/clamav
chmod 0770 /run/clamav

cat > /etc/clamav/clamd.conf <<'EOF'
DatabaseDirectory /var/lib/clamav
TCPSocket 3310
TCPAddr 127.0.0.1
StreamMaxLength 512M
MaxScanSize 512M
MaxFileSize 512M
MaxThreads 4
MaxQueue 10
EOF

cat > /run/clamav/clamdscan.conf <<'EOF'
TCPSocket 3310
TCPAddr 127.0.0.1
EOF
chmod 0644 /run/clamav/clamdscan.conf

# No media consumer starts until the signature database and daemon are ready.
gosu clamav freshclam --quiet

gosu clamav clamd --config-file=/etc/clamav/clamd.conf --foreground=true &
CLAMD_PID=$!
WORKER_PID=""

cleanup() {
  if [ -n "$WORKER_PID" ]; then
    kill "$WORKER_PID" 2>/dev/null || true
    wait "$WORKER_PID" 2>/dev/null || true
  fi
  kill "$CLAMD_PID" 2>/dev/null || true
  wait "$CLAMD_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

READY=0
for attempt in $(seq 1 60); do
  if gosu worker clamdscan --config-file=/run/clamav/clamdscan.conf --ping=1 >/dev/null 2>&1; then
    READY=1
    break
  fi
  if ! kill -0 "$CLAMD_PID" 2>/dev/null; then
    wait "$CLAMD_PID" || true
    echo "Content media worker disabled: ClamAV daemon exited during startup" >&2
    exit 1
  fi
  sleep 2
done

if [ "$READY" -ne 1 ]; then
  echo "Content media worker disabled: ClamAV daemon did not become ready" >&2
  exit 1
fi

ACTUAL_IDENTITY="$(gosu worker python - <<'PY'
import socket
from allpha_api.media_scanner import _parse_version

with socket.create_connection(("127.0.0.1", 3310), timeout=10) as connection:
    connection.sendall(b"zVERSION\\0")
    payload = connection.recv(4096)
engine, signature = _parse_version(payload)
print(f"{engine}|{signature}")
PY
)"
ACTUAL_ENGINE="${ACTUAL_IDENTITY%%|*}"
ACTUAL_SIGNATURE="${ACTUAL_IDENTITY#*|}"

if [ "$ACTUAL_ENGINE" != "$ALLPHA_DOCUMENT_SCANNER_ENGINE_VERSION" ] ||
   [ "$ACTUAL_SIGNATURE" != "$ALLPHA_DOCUMENT_SCANNER_SIGNATURE_VERSION" ]; then
  echo "Content media worker disabled: ClamAV engine/signature identity does not match the deployment pins" >&2
  exit 1
fi

export CLAMAV_HOST=127.0.0.1
echo "Pinned ClamAV scanner ready; starting canonical media consumers"
/usr/local/bin/shared-worker-entrypoint "$@" &
WORKER_PID=$!
wait "$WORKER_PID"
