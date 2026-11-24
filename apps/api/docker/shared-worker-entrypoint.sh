#!/bin/sh
set -eu

KNOWLEDGE_ENABLED="$(printf '%s' "${ALLPHA_KNOWLEDGE_DOCUMENT_WORKER_ENABLED:-false}" | tr '[:upper:]' '[:lower:]')"
SCANNER_MODE="$(printf '%s' "${ALLPHA_DOCUMENT_SCANNER_MODE:-}" | tr '[:upper:]' '[:lower:]')"
SCANNER_URL="${ALLPHA_DOCUMENT_SCANNER_URL:-}"
SCANNER_API_KEY="${ALLPHA_DOCUMENT_SCANNER_API_KEY:-}"
SCANNER_ALLOWED_HOSTS="${ALLPHA_DOCUMENT_SCANNER_ALLOWED_HOSTS:-}"

disable_knowledge_documents() {
    echo "$1" >&2
    export ALLPHA_KNOWLEDGE_DOCUMENT_WORKER_ENABLED=false
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
            # This shared host has a 1 GB memory ceiling. The production
            # signature database exceeds that budget; never start local clamd
            # here. A separate memory-eligible worker image owns that mode.
            disable_knowledge_documents "Knowledge document consumer disabled: local ClamAV is not supported on the resource-constrained shared worker; configure the authenticated remote scanner"
            ;;
        *)
            disable_knowledge_documents "Knowledge document consumer disabled: ALLPHA_DOCUMENT_SCANNER_MODE must be remote on the shared worker"
            ;;
    esac
fi

exec gosu worker "$@"
