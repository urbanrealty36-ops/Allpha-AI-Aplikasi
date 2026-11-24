#!/bin/sh
set -eu

KNOWLEDGE_ENABLED="$(printf '%s' "${ALLPHA_KNOWLEDGE_DOCUMENT_WORKER_ENABLED:-false}" | tr '[:upper:]' '[:lower:]')"
SCANNER_MODE="$(printf '%s' "${ALLPHA_DOCUMENT_SCANNER_MODE:-}" | tr '[:upper:]' '[:lower:]')"
SCANNER_URL="${ALLPHA_DOCUMENT_SCANNER_URL:-}"
SCANNER_API_KEY="${ALLPHA_DOCUMENT_SCANNER_API_KEY:-}"
SCANNER_ALLOWED_HOSTS="${ALLPHA_DOCUMENT_SCANNER_ALLOWED_HOSTS:-}"
CLAMAV_ENABLED="$(printf '%s' "${ALLPHA_CLAMAV_ENABLED:-false}" | tr '[:upper:]' '[:lower:]')"

disable_knowledge_documents() {
    echo "$1" >&2
    export ALLPHA_KNOWLEDGE_DOCUMENT_WORKER_ENABLED=false
}

start_local_clamav() {
    mkdir -p /run/clamav /var/log/clamav || return 1
    touch /var/log/clamav/clamav.log || return 1
    chown clamav:clamav /run/clamav /var/lib/clamav /var/log/clamav /var/log/clamav/clamav.log || return 1
    chmod 0770 /run/clamav || return 1

    # Scanner initialization must never terminate the other shared consumers.
    timeout 60s freshclam --quiet || return 1

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
    [ -s /run/clamav/clamd.conf ] || return 1

    cat > /run/clamav/clamdscan.conf <<'CLAMDSCAN_CONFIG'
LocalSocket /run/clamav/clamd.ctl
CLAMDSCAN_CONFIG
    [ -s /run/clamav/clamdscan.conf ] || return 1

    echo "Starting opt-in ClamAV daemon for Knowledge document scanning"
    gosu clamav clamd --config-file=/run/clamav/clamd.conf --foreground=true &
    CLAMD_PID=$!
    cleanup_clamd() {
        kill "$CLAMD_PID" 2>/dev/null || true
        wait "$CLAMD_PID" 2>/dev/null || true
    }
    trap cleanup_clamd EXIT INT TERM

    READY=0
    for attempt in $(seq 1 30); do
        if timeout 3s gosu worker clamdscan --config-file=/run/clamav/clamdscan.conf --ping=1 >/dev/null 2>&1; then
            READY=1
            break
        fi
        if [ $((attempt % 10)) -eq 0 ]; then
            echo "Waiting for ClamAV socket readiness: attempt $attempt/30"
        fi
        sleep 1
    done

    if [ "$READY" -ne 1 ]; then
        echo "ClamAV readiness failed; only the Knowledge document consumer will be disabled" >&2
        id worker >&2 || true
        ls -ld /run/clamav >&2 || true
        ls -la /run/clamav >&2 || true
        ps -o pid,ppid,rss,stat,comm -p "$CLAMD_PID" >&2 || true
        tail -n 80 /var/log/clamav/clamav.log >&2 || true
        cleanup_clamd
        trap - EXIT INT TERM
        return 1
    fi
    return 0
}

if [ "$KNOWLEDGE_ENABLED" = "true" ]; then
    case "$SCANNER_MODE" in
        remote)
            if [ -z "$SCANNER_URL" ] || [ -z "$SCANNER_API_KEY" ] || [ -z "$SCANNER_ALLOWED_HOSTS" ]; then
                disable_knowledge_documents "Knowledge document consumer disabled: remote scanner URL, API key and exact hostname allowlist are all required"
            elif ! gosu worker python -c 'from allpha_api.knowledge import RemoteDocumentScanner; RemoteDocumentScanner.from_environment()'; then
                disable_knowledge_documents "Knowledge document consumer disabled: remote scanner URL/HTTPS/allowlist configuration failed validation"
            else
                echo "Authenticated remote document scanner configuration validated"
            fi
            ;;
        clamd)
            if [ "$CLAMAV_ENABLED" != "true" ]; then
                disable_knowledge_documents "Knowledge document consumer disabled: local ClamAV must be explicitly enabled on a memory-eligible service"
            elif ! start_local_clamav; then
                disable_knowledge_documents "Knowledge document consumer disabled: local ClamAV could not initialize; other shared consumers will continue"
            else
                echo "ClamAV scanner is ready; starting shared Allpha consumers"
            fi
            ;;
        *)
            disable_knowledge_documents "Knowledge document consumer disabled: ALLPHA_DOCUMENT_SCANNER_MODE must be remote or clamd"
            ;;
    esac
fi

exec gosu worker "$@"
