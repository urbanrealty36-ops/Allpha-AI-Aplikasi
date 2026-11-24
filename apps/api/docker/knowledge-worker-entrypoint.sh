#!/bin/sh
set -eu

WORKER_ENABLED="$(printf '%s' "${ALLPHA_KNOWLEDGE_DOCUMENT_WORKER_ENABLED:-false}" | tr '[:upper:]' '[:lower:]')"
case "$WORKER_ENABLED" in
  true) ;;
  false)
    echo "Knowledge document consumer disabled; ClamAV bootstrap and job claims are skipped"
    exec sleep infinity
    ;;
  *)
    echo "ALLPHA_KNOWLEDGE_DOCUMENT_WORKER_ENABLED must be true or false" >&2
    exit 1
    ;;
esac

mkdir -p /run/clamav
chown clamav:clamav /run/clamav /var/lib/clamav
chmod 0770 /run/clamav

# Do not start document ingestion until a current local signature database and
# a responsive ClamAV daemon are available. Failure leaves every source quarantined.
freshclam --quiet

gosu clamav clamd --foreground=true &
CLAMD_PID=$!
cleanup() {
  kill "$CLAMD_PID" 2>/dev/null || true
  wait "$CLAMD_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

READY=0
for attempt in $(seq 1 60); do
  if gosu worker clamdscan --ping=1 >/dev/null 2>&1; then
    READY=1
    break
  fi
  if ! kill -0 "$CLAMD_PID" 2>/dev/null; then
    wait "$CLAMD_PID" || true
    echo "Knowledge worker disabled: ClamAV daemon exited during startup" >&2
    exit 1
  fi
  sleep 2
done

if [ "$READY" -ne 1 ]; then
  echo "Knowledge worker disabled: ClamAV daemon did not become ready" >&2
  exit 1
fi

export ALLPHA_DOCUMENT_SCANNER_MODE=clamd
exec gosu worker allpha-knowledge-ingestion-worker
