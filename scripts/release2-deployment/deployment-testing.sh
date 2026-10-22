#!/usr/bin/env bash
set -Eeuo pipefail

# Release 2 - Azure deployment smoke tests
# Tests the portal, five frontends and six backends.
# These are availability checks, not full CRUD/persistence tests.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

RESOURCE_GROUP="${RESOURCE_GROUP:-asd-release2-rg}"
APP_NAME="portal-frontend"
REPORT_FILE="$PROJECT_ROOT/reports/release2-deployment/deployment-results.md"

for tool in az curl; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "ERROR: Required tool not found: $tool" >&2
        exit 1
    fi
done

echo "=== Release 2 Deployment Testing ==="

if ! az group show \
    --name "$RESOURCE_GROUP" \
    --output none 2>/dev/null; then
    echo "ERROR: Resource group '$RESOURCE_GROUP' is inaccessible." >&2
    exit 1
fi

APP_HOST="$(az containerapp show \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query "properties.configuration.ingress.fqdn" \
    --output tsv)"

if [[ -z "$APP_HOST" || "$APP_HOST" == "None" ]]; then
    echo "ERROR: Could not retrieve the portal hostname." >&2
    exit 1
fi

FRONTEND_URL="https://${APP_HOST}"

echo "Portal: $FRONTEND_URL"
echo

# Format: Name|Path
CHECKS=(
    "Portal|/health"
    "Enrolment Frontend|/enrolment/"
    "Assessment Frontend|/assessments/"
    "Calendar Frontend|/calendar/"
    "Notebook Frontend|/notes/"
    "Exam Frontend|/exams/"
    "Authentication Backend|/auth-api/health"
    "Enrolment Backend|/enrolment-api/courses"
    "Assessment Backend|/assessments-api/assignments"
    "Calendar Backend|/calendar-api/events?student_id=1"
    "Notebook Backend|/notes-api/notebooks"
    "Exam Backend|/exams-api/"
)

mkdir -p "$(dirname "$REPORT_FILE")"

TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

cat > "$REPORT_FILE" <<EOF
# Release 2 Deployment Test Report

## Deployment Information

- **Resource Group:** $RESOURCE_GROUP
- **Portal Container App:** $APP_NAME
- **Portal URL:** $FRONTEND_URL
- **Timestamp (UTC):** $TIMESTAMP

## HTTP Validation Results

| Service | Endpoint | HTTP Status | Result |
|---|---|---|---|
EOF

PASSED=0
FAILED=0

for CHECK in "${CHECKS[@]}"; do
    NAME="${CHECK%%|*}"
    PATH_VALUE="${CHECK#*|}"
    URL="${FRONTEND_URL}${PATH_VALUE}"

    HTTP_STATUS="$(curl \
        --silent \
        --show-error \
        --output /dev/null \
        --write-out "%{http_code}" \
        --location \
        --connect-timeout 10 \
        --max-time 30 \
        "$URL")" || HTTP_STATUS="000"

    if [[ "$HTTP_STATUS" == "200" ]]; then
        RESULT="PASS"
        PASSED=$((PASSED + 1))
    else
        RESULT="FAIL"
        FAILED=$((FAILED + 1))
    fi

    printf '%-26s HTTP %-3s %s\n' \
        "$NAME" "$HTTP_STATUS" "$RESULT"

    printf '| %s | `%s` | %s | %s |\n' \
        "$NAME" "$PATH_VALUE" "$HTTP_STATUS" "$RESULT" \
        >> "$REPORT_FILE"
done

TOTAL="${#CHECKS[@]}"

if [[ "$FAILED" -eq 0 ]]; then
    OVERALL="PASS"
else
    OVERALL="FAIL"
fi

cat >> "$REPORT_FILE" <<EOF

## Summary

- **Total Checks:** $TOTAL
- **Passed:** $PASSED
- **Failed:** $FAILED
- **Overall Status:** $OVERALL

## Test Scope

These smoke tests verify that:
- The shared portal is reachable over HTTPS.
- All five student frontend routes return HTTP 200.
- All six backend endpoints return HTTP 200 through the portal.
- Selected read-only backend routes can be reached.

These tests do not establish:
- Complete CRUD functionality.
- Successful browser rendering of JavaScript and CSS.
- Authentication and authorisation correctness.
- Database persistence across Azure Container App recreation.
- Azure Files reliability under concurrent access.

## Reviewer Notes

Pending /review-deployment review.
EOF

echo
echo "=== Deployment Testing Complete ==="
echo "Passed: $PASSED/$TOTAL"
echo "Failed: $FAILED"
echo "Overall: $OVERALL"
echo "Report: $REPORT_FILE"

if [[ "$FAILED" -ne 0 ]]; then
    exit 1
fi
