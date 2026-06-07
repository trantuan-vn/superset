#!/usr/bin/env bash
# Issue a client test certificate from the local Step CA (auth-test stack).
# Usage: ./issue-test-cert.sh <common-name> [san-email]
# Example: ./issue-test-cert.sh cntt.cv cntt.cv@demo-corp.local
#
# Does not require `step` on the host — uses docker exec portal-auth-step-ca by default.
set -euo pipefail

CN="${1:?Common name required, e.g. cntt.cv}"
EMAIL="${2:-${CN}@demo-corp.local}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PKI_DIR="$(cd "${SCRIPT_DIR}/../pki" && pwd)"
OUT_DIR="${PKI_DIR}/certs"
ROOT_CA="${PKI_DIR}/root_ca.crt"
FINGERPRINT_FILE="${PKI_DIR}/ca_fingerprint.txt"

STEP_CA_CONTAINER="${STEP_CA_CONTAINER:-portal-auth-step-ca}"
STEP_CA_URL_HOST="${STEP_CA_URL:-https://localhost:9443}"
# Inside the step-ca container the API listens on :9000
STEP_CA_URL_INTERNAL="${STEP_CA_URL_INTERNAL:-https://localhost:9000}"
STEP_CA_PROVISIONER="${STEP_CA_PROVISIONER:-portal-admin}"
STEP_CA_PROVISIONER_PASSWORD="${STEP_CA_PROVISIONER_PASSWORD:-changeit}"
STEP_CA_FINGERPRINT="${STEP_CA_FINGERPRINT:-}"

mkdir -p "${OUT_DIR}"

if [[ -z "${STEP_CA_FINGERPRINT}" && -f "${FINGERPRINT_FILE}" ]]; then
  STEP_CA_FINGERPRINT="$(tr -d '[:space:]' < "${FINGERPRINT_FILE}")"
fi

if [[ -z "${STEP_CA_FINGERPRINT}" && -f "${ROOT_CA}" ]] && command -v step >/dev/null 2>&1; then
  STEP_CA_FINGERPRINT="$(step certificate fingerprint "${ROOT_CA}")"
fi

if [[ -z "${STEP_CA_FINGERPRINT}" ]]; then
  echo "Run auth-test bootstrap first:" >&2
  echo "  docker compose -f portal/docker/docker-compose.auth-test.yml up -d step-ca" >&2
  echo "  docker compose -f portal/docker/docker-compose.auth-test.yml run --rm step-ca-bootstrap" >&2
  exit 1
fi

if ! docker ps --format '{{.Names}}' | grep -qx "${STEP_CA_CONTAINER}"; then
  echo "Container ${STEP_CA_CONTAINER} is not running. Start auth-test stack first." >&2
  exit 1
fi

CRT_BASENAME="${CN}.crt"
KEY_BASENAME="${CN}.key"
CRT_HOST="${OUT_DIR}/${CRT_BASENAME}"
KEY_HOST="${OUT_DIR}/${KEY_BASENAME}"

# Non-interactive: -i without -t; --force skips overwrite prompt (no /dev/tty needed).
docker exec -i "${STEP_CA_CONTAINER}" sh -c "
  set -e
  mkdir -p /home/step/export/certs
  echo '${STEP_CA_PROVISIONER_PASSWORD}' > /tmp/step-ca-pass
  step ca certificate '${CN}' \
    /home/step/export/certs/${CRT_BASENAME} \
    /home/step/export/certs/${KEY_BASENAME} \
    --ca-url '${STEP_CA_URL_INTERNAL}' \
    --provisioner '${STEP_CA_PROVISIONER}' \
    --provisioner-password-file /tmp/step-ca-pass \
    --not-after 24h \
    --san '${CN}@demo-corp.local' \
    --san '${EMAIL}' \
    --force
  rm -f /tmp/step-ca-pass
" </dev/null

echo "Issued certificate and private key:"
echo "  ${CRT_HOST}"
echo "  ${KEY_HOST}"
echo ""
echo "PKI login (Portal dev): upload both files on /login/pki"
echo "Optional — install step CLI on macOS: brew install step"
