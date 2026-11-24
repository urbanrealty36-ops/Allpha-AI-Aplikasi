#!/bin/sh
set -eu

KNOWLEDGE_ENABLED="$(printf '%s' "${ALLPHA_KNOWLEDGE_DOCUMENT_WORKER_ENABLED:-false}" | tr '[:upper:]' '[:lower:]')"
SCANNER_MODE="$(printf '%s' "${ALLPHA_DOCUMENT_SCANNER_MODE:-}" | tr '[:upper:]' '[:lower:]')"
SCANNER_URL="${ALLPHA_DOCUMENT_SCANNER_URL:-}"

if [ "$KNOWLEDGE_ENABLED" = "true" ] && [ -z "$SCANNER_URL" ] && [ "$SCANNER_MODE" = "clamd" ]; then
    mkdir -p /run/clamav
    mkdir -p /var/log/clamav
    touch /var/log/clamav/clamav.log
    chown clamav:clamav /run/clamav /var/lib/clamav /var/log/clamav /var/log/clamav/clamav.log
    chmod 0770 /run/clamav

    # Do not start the Knowledge consumer with stale or missing malware signatures.
    freshclam --quiet

    # Use a minimal explicit daemon configuration instead of a distro sample file.
    cat > /run/clamav/clamd.conf <<'CLAMD_CONFIG'
DatabaseDirectory /var/lib/clamav
Foreground yes
LogTime yes
LogVerbose yes
LogFile /var/log/clamav/clamav.log
LocalSocket /run/clamav/clamd.ctl
LocalSocketGroup clamav
LocalSocketMode 660
FixStaleSocket yes
MaxFileSize 10M
MaxScanSize 20M
StreamMaxLength 20M
MaxThreads 1
MaxConnectionQueueLength 4
MaxQueue 8
MaxRecursion 8
MaxFiles 200
MaxDirectoryRecursion 5
ConcurrentDatabaseReload no
SelfCheck 3600
CLAMD_CONFIG

    cat > /run/clamav/clamdscan.conf <<'CLAMDSCAN_CONFIG'
LocalSocket /run/clamav/clamd.ctl
CLAMDSCAN_CONFIG

    echo "Starting ClamAV daemon for Knowledge document scanning"
    gosu clamav clamd --config-file=/run/clamav/clamd.conf --foreground=true &
    CLAMD_PID=$!
    cleanup() {
        kill "$CLAMD_PID" 2>/dev/null || true
        wait "$CLAMD_PID" 2>/dev/null || true
    }
    trap cleanup EXIT INT TERM

    READY=0
    for attempt in $(seq 1 30); do
        if timeout 3s gosu worker clamdscan --config-file=/run/clamav/clamdscan.conf --ping=1; then
            READY=1
            break
        fi
        if [ $((attempt % 10)) -eq 0 ]; then
            echo "Waiting for ClamAV socket readiness: attempt $attempt/30"
        fi
        sleep 1
    done

    if [ "$READY" -ne 1 ]; then
        echo "Knowledge document consumer disabled: ClamAV daemon did not become ready; other shared consumers will continue" >&2
        echo "ClamAV worker identity and socket diagnostics:" >&2
        id worker >&2 || true
        ls -ld /run/clamav >&2 || true
        ls -la /run/clamav >&2 || true
        ps -o pid,ppid,rss,stat,comm -p "$CLAMD_PID" >&2 || true
        tail -n 80 /var/log/clamav/clamav.log >&2 || true
        export ALLPHA_KNOWLEDGE_DOCUMENT_WORKER_ENABLED=false
    else
        echo "ClamAV scanner is ready; starting shared Allpha consumers"
    fi
fi

exec gosu worker "$@"
