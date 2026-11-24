#!/bin/sh
set -eu

KNOWLEDGE_ENABLED="$(printf '%s' "${ALLPHA_KNOWLEDGE_DOCUMENT_WORKER_ENABLED:-false}" | tr '[:upper:]' '[:lower:]')"
SCANNER_MODE="$(printf '%s' "${ALLPHA_DOCUMENT_SCANNER_MODE:-}" | tr '[:upper:]' '[:lower:]')"
SCANNER_URL="${ALLPHA_DOCUMENT_SCANNER_URL:-}"

if [ "$KNOWLEDGE_ENABLED" = "true" ] && [ -z "$SCANNER_URL" ] && [ "$SCANNER_MODE" = "clamd" ]; then
    mkdir -p /run/clamav
    chown clamav:clamav /run/clamav /var/lib/clamav
    chmod 0770 /run/clamav

    # Do not start the Knowledge consumer with stale or missing malware signatures.
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
            echo "Shared worker disabled: ClamAV daemon exited during startup" >&2
            exit 1
        fi
        sleep 2
    done

    if [ "$READY" -ne 1 ]; then
        echo "Shared worker disabled: ClamAV daemon did not become ready" >&2
        exit 1
    fi
fi

exec gosu worker "$@"
