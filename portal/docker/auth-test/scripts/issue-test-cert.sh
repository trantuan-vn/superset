#!/usr/bin/env bash
# Issue a client test certificate from the local Step CA (auth-test stack).
# Usage: ./issue-test-cert.sh <common-name> [san-email]
# Example: ./issue-test-cert.sh cntt.cv cntt.cv@demo-corp.local
set -euo pipefail

CN="${1:?Common name required, e.g. cntt.cv}"
EMAIL="${2:-${CN}@demo-corp.local}"
OUT_DIR="$(cd "$(dirname "$0")/../pki/certs" && pwd)"
STEP_CA_URL="${STEP_CA_URL:-https://localhost:9443}"
STEP_CA_FINGERPRINT="${STEP_CA_FINGERPRINT:-}"

mkdir -p "${OUT_DIR}"

if [[ -z "${STEP_CA_FINGERPRINT}" ]]; then
  echo "Set STEP_CA_FINGERPRINT from: docker compose -f portal/docker/docker-compose.auth-test.yml logs step-ca"
  echo "Or run: step ca fingerprint --ca-url ${STEP_CA_URL} --root portal/docker/auth-test/pki/root_ca.crt"
  exit 1
fi

step ca certificate "${OUT_DIR}/${CN}.crt" "${OUT_DIR}/${CN}.csr" \
  --ca-url "${STEP_CA_URL}" \
  --fingerprint "${STEP_CA_FINGERPRINT}" \
  --not-after 24h \
  --san "${CN}@demo-corp.local" \
  --san "${EMAIL}" \
  --force

echo "Issued: ${OUT_DIR}/${CN}.crt (import into browser or use with OpenSSL tests)"
