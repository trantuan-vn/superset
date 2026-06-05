#!/usr/bin/env bash
#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
set -euo pipefail

BUNDLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=lib.sh
source "${BUNDLE_DIR}/lib.sh"

kbundle_require_cmd docker
kbundle_require_cmd kubectl
kbundle_require_cmd helm

[[ -f "${BUNDLE_DIR}/bundle.conf" ]] || kbundle_die "Không tìm thấy bundle.conf"
[[ -f "${BUNDLE_DIR}/images.manifest" ]] || kbundle_die "Không tìm thấy images.manifest"

# shellcheck source=/dev/null
source "${BUNDLE_DIR}/bundle.conf"

STATE_FILE="${BUNDLE_DIR}/.deploy-state.env"
VALUES_FILE="${BUNDLE_DIR}/helm/values.yaml"
HELM_CHART="${BUNDLE_DIR}/${HELM_CHART_PATH:-helm/superset}"
FORCE_HELM_UPGRADE="${FORCE_HELM_UPGRADE:-false}"
SKIP_DOCKER_PUSH="${SKIP_DOCKER_PUSH:-false}"

# --- Thu thập deploy.env (interactive lần đầu) ---
collect_deploy_env() {
  if [[ -f "${BUNDLE_DIR}/deploy.env" ]]; then
    # shellcheck source=/dev/null
    source "${BUNDLE_DIR}/deploy.env"
    return
  fi

  echo "=== Cấu hình deploy (lần đầu) ==="
  cp "${BUNDLE_DIR}/deploy.env.example" "${BUNDLE_DIR}/deploy.env"

  read -r -p "SUPERSET_SECRET_KEY (openssl rand -base64 42): " SUPERSET_SECRET_KEY
  [[ -n "${SUPERSET_SECRET_KEY}" ]] || kbundle_die "Thiếu SUPERSET_SECRET_KEY"

  read -r -p "ADMIN_PASSWORD [admin]: " ADMIN_PASSWORD
  ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"

  read -r -p "INGRESS_HOST (vd superset.example.com): " INGRESS_HOST
  [[ -n "${INGRESS_HOST}" ]] || kbundle_die "Thiếu INGRESS_HOST"

  read -r -p "INGRESS_CLASS [nginx]: " INGRESS_CLASS
  INGRESS_CLASS="${INGRESS_CLASS:-nginx}"

  read -r -p "HELM_NAMESPACE [${HELM_NAMESPACE}]: " input_ns
  HELM_NAMESPACE="${input_ns:-${HELM_NAMESPACE}}"

  read -r -p "HELM_RELEASE [${HELM_RELEASE}]: " input_rel
  HELM_RELEASE="${input_rel:-${HELM_RELEASE}}"

  read -r -p "SKIP_DOCKER_PUSH (true/false) [false]: " SKIP_DOCKER_PUSH
  SKIP_DOCKER_PUSH="${SKIP_DOCKER_PUSH:-false}"

  read -r -p "FORCE_HELM_UPGRADE (true/false) [false]: " FORCE_HELM_UPGRADE
  FORCE_HELM_UPGRADE="${FORCE_HELM_UPGRADE:-false}"

  cat > "${BUNDLE_DIR}/deploy.env" <<EOF
SUPERSET_SECRET_KEY=${SUPERSET_SECRET_KEY}
ADMIN_PASSWORD=${ADMIN_PASSWORD}
INGRESS_HOST=${INGRESS_HOST}
INGRESS_CLASS=${INGRESS_CLASS}
HELM_NAMESPACE=${HELM_NAMESPACE}
HELM_RELEASE=${HELM_RELEASE}
SKIP_DOCKER_PUSH=${SKIP_DOCKER_PUSH}
FORCE_HELM_UPGRADE=${FORCE_HELM_UPGRADE}
USE_BUNDLED_INFRA=true
EOF

  # shellcheck source=/dev/null
  source "${BUNDLE_DIR}/deploy.env"
}

collect_deploy_env

HELM_NAMESPACE="${HELM_NAMESPACE:-superset}"
HELM_RELEASE="${HELM_RELEASE:-superset}"
FORCE_HELM_UPGRADE="${FORCE_HELM_UPGRADE:-false}"
SKIP_DOCKER_PUSH="${SKIP_DOCKER_PUSH:-false}"

[[ -f "${VALUES_FILE}" ]] || kbundle_die "Không tìm thấy helm/values.yaml"
[[ -d "${HELM_CHART}" ]] || kbundle_die "Không tìm thấy Helm chart: ${HELM_CHART}"

if [[ "${SUPERSET_SECRET_KEY:-}" == *CHANGE_ME* ]] || [[ -z "${SUPERSET_SECRET_KEY:-}" ]]; then
  kbundle_die "Đặt SUPERSET_SECRET_KEY trong deploy.env"
fi

echo "=============================================="
echo " Superset K8s Deploy (smart skip)"
echo "=============================================="
echo " Bundle Superset   : ${SUPERSET_IMAGE}"
echo " Bundle WebSocket  : ${WEBSOCKET_IMAGE:-n/a}"
echo " Namespace         : ${HELM_NAMESPACE}"
echo " State file        : ${STATE_FILE}"
echo "=============================================="
echo ""

# --- Bước 1: Load & push images (skip nếu version không đổi) ---
echo "==> [1/3] Xử lý images (skip nếu version đã deploy)..."

kbundle_load_push_image "app" "${SUPERSET_IMAGE}" \
  "${BUNDLE_DIR}/images/superset-${IMAGE_TAG}.tar" \
  "SUPERSET_IMAGE" "${STATE_FILE}" "${SKIP_DOCKER_PUSH}"

if [[ -f "${BUNDLE_DIR}/images/websocket-${IMAGE_TAG}.tar" ]]; then
  kbundle_load_push_image "app-websocket" "${WEBSOCKET_IMAGE}" \
    "${BUNDLE_DIR}/images/websocket-${IMAGE_TAG}.tar" \
    "WEBSOCKET_IMAGE" "${STATE_FILE}" "${SKIP_DOCKER_PUSH}"
fi

kbundle_load_push_image "infra-postgres" "${POSTGRES_IMAGE}" \
  "${BUNDLE_DIR}/images/postgres-${POSTGRES_TAG:-17}.tar" \
  "POSTGRES_IMAGE" "${STATE_FILE}" "${SKIP_DOCKER_PUSH}"

kbundle_load_push_image "infra-redis" "${REDIS_IMAGE}" \
  "${BUNDLE_DIR}/images/redis-${REDIS_TAG:-7}.tar" \
  "REDIS_IMAGE" "${STATE_FILE}" "${SKIP_DOCKER_PUSH}"

kbundle_load_push_image "infra-dockerize" "${DOCKERIZE_IMAGE}" \
  "${BUNDLE_DIR}/images/dockerize-${DOCKERIZE_TAG:-dockerize}.tar" \
  "DOCKERIZE_IMAGE" "${STATE_FILE}" "${SKIP_DOCKER_PUSH}"

NGINX_TAR="$(find "${BUNDLE_DIR}/images" -name 'nginx-*.tar' 2>/dev/null | head -1 || true)"
if [[ "${INCLUDE_NGINX:-no}" =~ ^[Yy] ]] && [[ -n "${NGINX_TAR}" ]]; then
  kbundle_load_push_image "infra-nginx" "${NGINX_IMAGE}" \
    "${NGINX_TAR}" "NGINX_IMAGE" "${STATE_FILE}" "${SKIP_DOCKER_PUSH}"
fi

# --- Bước 2: Kiểm tra có cần helm upgrade không ---
echo ""
echo "==> [2/3] Kiểm tra thay đổi version..."

NEED_HELM_UPGRADE=false
REASONS=()

if [[ "${FORCE_HELM_UPGRADE}" == "true" ]]; then
  NEED_HELM_UPGRADE=true
  REASONS+=("FORCE_HELM_UPGRADE=true")
fi

if ! kbundle_version_unchanged "SUPERSET_IMAGE" "${SUPERSET_IMAGE}" "${STATE_FILE}"; then
  NEED_HELM_UPGRADE=true
  REASONS+=("Superset image đổi → ${SUPERSET_IMAGE}")
fi

if [[ -n "${WEBSOCKET_IMAGE:-}" ]] && \
  ! kbundle_version_unchanged "WEBSOCKET_IMAGE" "${WEBSOCKET_IMAGE}" "${STATE_FILE}"; then
  NEED_HELM_UPGRADE=true
  REASONS+=("WebSocket image đổi → ${WEBSOCKET_IMAGE}")
fi

NEED_INFRA_APPLY=false
if ! kbundle_version_unchanged "POSTGRES_IMAGE" "${POSTGRES_IMAGE}" "${STATE_FILE}"; then
  NEED_HELM_UPGRADE=true
  NEED_INFRA_APPLY=true
  REASONS+=("PostgreSQL image đổi")
fi

if ! kbundle_version_unchanged "REDIS_IMAGE" "${REDIS_IMAGE}" "${STATE_FILE}"; then
  NEED_HELM_UPGRADE=true
  NEED_INFRA_APPLY=true
  REASONS+=("Redis image đổi")
fi

if ! kbundle_version_unchanged "DOCKERIZE_IMAGE" "${DOCKERIZE_IMAGE}" "${STATE_FILE}"; then
  NEED_HELM_UPGRADE=true
  REASONS+=("Dockerize image đổi")
fi

if ! kbundle_version_unchanged "HELM_CHART_VERSION" "${HELM_CHART_VERSION}" "${STATE_FILE}"; then
  NEED_HELM_UPGRADE=true
  REASONS+=("Helm chart version đổi")
fi

if [[ ! -f "${STATE_FILE}" ]] || ! grep -q "LAST_DEPLOY_SUCCESS=true" "${STATE_FILE}" 2>/dev/null; then
  NEED_HELM_UPGRADE=true
  NEED_INFRA_APPLY=true
  REASONS+=("Chưa deploy thành công lần nào")
fi

if [[ "${NEED_HELM_UPGRADE}" == "false" ]]; then
  echo ""
  echo "=============================================="
  echo " KHÔNG CÓ THAY ĐỔI VERSION"
  echo "=============================================="
  echo " Tất cả image infra + app đã deploy với cùng version."
  echo " Bỏ qua helm upgrade."
  echo ""
  echo " Muốn deploy lại: FORCE_HELM_UPGRADE=true ./deploy.sh"
  echo " Muốn upgrade Superset code: tăng IMAGE_TAG trong build-bundle.sh"
  exit 0
fi

echo " Cần helm upgrade vì:"
for r in "${REASONS[@]}"; do
  echo "   - ${r}"
done

# --- Bước 2b: Deploy infra postgres/redis (official images) ---
if [[ "${NEED_INFRA_APPLY}" == "true" ]] && [[ -d "${BUNDLE_DIR}/infra" ]]; then
  echo ""
  echo "==> [2b/3] Apply infra manifests (postgres + redis)..."
  kubectl apply -f "${BUNDLE_DIR}/infra/" -n "${HELM_NAMESPACE}" --create-namespace
else
  echo ""
  echo "==> [2b/3] Skip infra apply (postgres/redis version không đổi)"
fi

# --- Bước 3: Helm deploy (offline chart) ---
echo ""
echo "==> [3/3] Helm upgrade (chart offline trong bundle)..."

HELM_SET_ARGS=(
  --set "image.repository=${IMAGE_REPOSITORY}"
  --set "image.tag=${IMAGE_TAG}"
  --set "extraSecretEnv.SUPERSET_SECRET_KEY=${SUPERSET_SECRET_KEY}"
  --set "init.adminUser.password=${ADMIN_PASSWORD}"
  --set "ingress.hosts[0]=${INGRESS_HOST}"
  --set "ingress.ingressClassName=${INGRESS_CLASS:-nginx}"
  --set "initImage.repository=${IMAGE_REGISTRY}/${DOCKERIZE_REPO:-superset-dockerize}"
  --set "initImage.tag=${DOCKERIZE_TAG:-dockerize}"
  --set "postgresql.enabled=false"
  --set "redis.enabled=false"
)

if [[ -n "${WEBSOCKET_IMAGE:-}" ]]; then
  HELM_SET_ARGS+=(
    --set "supersetWebsockets.enabled=true"
    --set "supersetWebsockets.image.repository=${IMAGE_REGISTRY}/${WEBSOCKET_REPO:-superset-websocket}"
    --set "supersetWebsockets.image.tag=${IMAGE_TAG}"
  )
fi

helm upgrade --install "${HELM_RELEASE}" "${HELM_CHART}" \
  -f "${VALUES_FILE}" \
  "${HELM_SET_ARGS[@]}" \
  -n "${HELM_NAMESPACE}" \
  --create-namespace

kbundle_save_deploy_state "${STATE_FILE}" \
  "SUPERSET_IMAGE" "${SUPERSET_IMAGE}" \
  "WEBSOCKET_IMAGE" "${WEBSOCKET_IMAGE:-none}" \
  "POSTGRES_IMAGE" "${POSTGRES_IMAGE}" \
  "REDIS_IMAGE" "${REDIS_IMAGE}" \
  "DOCKERIZE_IMAGE" "${DOCKERIZE_IMAGE}" \
  "NGINX_IMAGE" "${NGINX_IMAGE:-none}" \
  "HELM_CHART_VERSION" "${HELM_CHART_VERSION}" \
  "HELM_RELEASE" "${HELM_RELEASE}" \
  "HELM_NAMESPACE" "${HELM_NAMESPACE}" \
  "LAST_DEPLOY_SUCCESS" "true" \
  "LAST_DEPLOY_DATE" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo ""
echo "=============================================="
echo " DEPLOY HOÀN TẤT"
echo "=============================================="
echo " kubectl get pods -n ${HELM_NAMESPACE}"
echo " kubectl port-forward -n ${HELM_NAMESPACE} svc/${HELM_RELEASE} 8088:8088"
echo ""
