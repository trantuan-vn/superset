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

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# shellcheck source=images.def.sh
source "${SCRIPT_DIR}/images.def.sh"
# shellcheck source=lib.sh
source "${SCRIPT_DIR}/lib.sh"

prompt() {
  local var_name="$1"
  local default="$2"
  local label="$3"
  local value
  read -r -p "${label} [${default}]: " value
  if [[ -z "${value}" ]]; then
    value="${default}"
  fi
  printf -v "${var_name}" '%s' "${value}"
}

pull_tag_save() {
  local source_image="$1"
  local target_image="$2"
  local tar_path="$3"
  local role="$4"

  echo "    Pull  ${source_image}"
  docker pull "${source_image}"
  docker tag "${source_image}" "${target_image}"
  docker save -o "${tar_path}" "${target_image}"
  echo "    Saved ${tar_path} ($(du -h "${tar_path}" | cut -f1))"
  echo "${role}|${source_image}|${target_image}|${tar_path}" >> "${MANIFEST_FILE}"
}

echo "=============================================="
echo " Superset K8s Bundle Builder (full stack)"
echo "=============================================="
echo ""

prompt IMAGE_REGISTRY "docker.io/tuantahp" "Docker registry (không có / ở cuối)"
prompt IMAGE_TAG "1.0.0" "Superset image tag (đổi khi có code mới)"
prompt BUNDLE_PARENT_DIR "${ROOT}/dist" "Thư mục output bundle"
prompt HELM_NAMESPACE "superset" "K8s namespace"
prompt HELM_RELEASE "superset" "Helm release name"
prompt INCLUDE_NGINX "yes" "Đóng gói image nginx? (yes/no)"

IMAGE_REPOSITORY="${IMAGE_REGISTRY}/superset"
SUPERSET_IMAGE="${IMAGE_REPOSITORY}:${IMAGE_TAG}"
BUNDLE_DIR="${BUNDLE_PARENT_DIR}/superset-k8s-bundle-${IMAGE_TAG}"
IMAGES_DIR="${BUNDLE_DIR}/images"
MANIFEST_FILE="${BUNDLE_DIR}/images.manifest"

WEBSOCKET_IMAGE="${IMAGE_REGISTRY}/${WEBSOCKET_REPO}:${IMAGE_TAG}"
POSTGRES_IMAGE="${IMAGE_REGISTRY}/${POSTGRES_REPO}:${POSTGRES_TAG}"
REDIS_IMAGE="${IMAGE_REGISTRY}/${REDIS_REPO}:${REDIS_TAG}"
DOCKERIZE_IMAGE="${IMAGE_REGISTRY}/${DOCKERIZE_REPO}:${DOCKERIZE_TAG}"
NGINX_IMAGE="${IMAGE_REGISTRY}/${NGINX_REPO}:${NGINX_TAG}"

echo ""
echo "--- Xác nhận (đồng bộ docker-compose local dev) ---"
echo "  Superset app    : ${SUPERSET_IMAGE}  (→ node + worker + beat)"
echo "  Superset WS     : ${WEBSOCKET_IMAGE}"
echo "  PostgreSQL      : ${POSTGRES_IMAGE}  (postgres:17)"
echo "  Redis           : ${REDIS_IMAGE}  (redis:7)"
echo "  Dockerize       : ${DOCKERIZE_IMAGE}"
if [[ "${INCLUDE_NGINX}" =~ ^[Yy] ]]; then
  echo "  Nginx           : ${NGINX_IMAGE}  (nginx:latest)"
fi
echo "  (KHÔNG đóng gói superset-node — chỉ dùng dev webpack)"
echo "  Helm chart      : ${HELM_CHART_VERSION}"
echo "  Bundle dir      : ${BUNDLE_DIR}"
echo ""
read -r -p "Tiếp tục? [Y/n]: " confirm
if [[ "${confirm}" =~ ^[Nn] ]]; then
  echo "Đã hủy."
  exit 0
fi

mkdir -p "${IMAGES_DIR}" "${BUNDLE_DIR}/helm" "${BUNDLE_DIR}/infra"

echo ""
echo "==> [1/6] Build Superset app từ source (--target prod)..."
echo "         (dùng chung cho superset + worker + worker-beat)"
docker build --target prod \
  --build-arg DEV_MODE=false \
  -t "${SUPERSET_IMAGE}" \
  "${ROOT}"

echo ""
echo "==> [2/6] Build Superset WebSocket từ source..."
docker build -t "${WEBSOCKET_IMAGE}" "${ROOT}/superset-websocket"

echo ""
echo "==> [3/6] Export app images..."
SUPERSET_TAR="${IMAGES_DIR}/superset-${IMAGE_TAG}.tar"
WEBSOCKET_TAR="${IMAGES_DIR}/websocket-${IMAGE_TAG}.tar"
docker save -o "${SUPERSET_TAR}" "${SUPERSET_IMAGE}"
docker save -o "${WEBSOCKET_TAR}" "${WEBSOCKET_IMAGE}"
echo "    ${SUPERSET_TAR} ($(du -h "${SUPERSET_TAR}" | cut -f1))"
echo "    ${WEBSOCKET_TAR} ($(du -h "${WEBSOCKET_TAR}" | cut -f1))"

echo ""
echo "==> [4/6] Pull & export infra images (postgres:17, redis:7, nginx)..."
: > "${MANIFEST_FILE}"
echo "app|built-local|${SUPERSET_IMAGE}|${SUPERSET_TAR}" >> "${MANIFEST_FILE}"
echo "app|built-local|${WEBSOCKET_IMAGE}|${WEBSOCKET_TAR}" >> "${MANIFEST_FILE}"

pull_tag_save "${POSTGRES_SOURCE}" "${POSTGRES_IMAGE}" \
  "${IMAGES_DIR}/postgres-${POSTGRES_TAG}.tar" "infra-postgres"

pull_tag_save "${REDIS_SOURCE}" "${REDIS_IMAGE}" \
  "${IMAGES_DIR}/redis-${REDIS_TAG}.tar" "infra-redis"

pull_tag_save "${DOCKERIZE_SOURCE}" "${DOCKERIZE_IMAGE}" \
  "${IMAGES_DIR}/dockerize-${DOCKERIZE_TAG}.tar" "infra-dockerize"

if [[ "${INCLUDE_NGINX}" =~ ^[Yy] ]]; then
  pull_tag_save "${NGINX_SOURCE}" "${NGINX_IMAGE}" \
    "${IMAGES_DIR}/nginx-${NGINX_TAG}.tar" "infra-nginx"
fi

echo ""
echo "==> [5/6] Download Helm chart (offline)..."
kbundle_require_cmd helm
helm repo add superset https://apache.github.io/superset 2>/dev/null || true
helm repo update
rm -rf "${BUNDLE_DIR}/helm/superset"
helm pull superset/superset \
  --version "${HELM_CHART_VERSION}" \
  --untar \
  --destination "${BUNDLE_DIR}/helm"
cd "${BUNDLE_DIR}/helm/superset"
helm dependency build
cd "${ROOT}"

echo ""
echo "==> [6/6] Tạo infra manifests + Helm values + deploy kit..."

# Infra postgres/redis — dùng official images như docker-compose (không dùng Bitnami subchart)
cat > "${BUNDLE_DIR}/infra/postgres.yaml" <<PG_EOF
apiVersion: v1
kind: Service
metadata:
  name: ${INFRA_POSTGRES_SERVICE}
spec:
  ports:
    - port: 5432
      targetPort: 5432
  selector:
    app: superset-postgres
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: superset-postgres
spec:
  serviceName: ${INFRA_POSTGRES_SERVICE}
  replicas: 1
  selector:
    matchLabels:
      app: superset-postgres
  template:
    metadata:
      labels:
        app: superset-postgres
    spec:
      containers:
        - name: postgres
          image: ${POSTGRES_IMAGE}
          ports:
            - containerPort: 5432
          env:
            - name: POSTGRES_USER
              value: superset
            - name: POSTGRES_PASSWORD
              value: superset
            - name: POSTGRES_DB
              value: superset
          volumeMounts:
            - name: data
              mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
    - metadata:
        name: data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 10Gi
PG_EOF

cat > "${BUNDLE_DIR}/infra/redis.yaml" <<REDIS_EOF
apiVersion: v1
kind: Service
metadata:
  name: ${INFRA_REDIS_SERVICE}
spec:
  ports:
    - port: 6379
      targetPort: 6379
  selector:
    app: superset-redis
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: superset-redis
spec:
  replicas: 1
  selector:
    matchLabels:
      app: superset-redis
  template:
    metadata:
      labels:
        app: superset-redis
    spec:
      containers:
        - name: redis
          image: ${REDIS_IMAGE}
          ports:
            - containerPort: 6379
REDIS_EOF

cat > "${BUNDLE_DIR}/helm/values.yaml" <<VALUES_EOF
# Generated by build-bundle.sh — khớp docker-compose local dev
image:
  repository: ${IMAGE_REPOSITORY}
  tag: "${IMAGE_TAG}"
  pullPolicy: IfNotPresent

runAsUser: 1000

initImage:
  repository: ${IMAGE_REGISTRY}/${DOCKERIZE_REPO}
  tag: ${DOCKERIZE_TAG}

# Dùng infra/postgres.yaml + infra/redis.yaml thay vì Bitnami subchart
postgresql:
  enabled: false

redis:
  enabled: false

supersetNode:
  replicas:
    replicaCount: 2
  connections:
    db_type: postgresql
    db_host: ${INFRA_POSTGRES_SERVICE}
    db_port: "5432"
    db_user: superset
    db_pass: superset
    db_name: superset
    redis_host: ${INFRA_REDIS_SERVICE}
    redis_port: "6379"
  resources:
    requests:
      cpu: "500m"
      memory: "1Gi"
    limits:
      memory: "2Gi"

supersetWorker:
  replicas:
    replicaCount: 2

supersetCeleryBeat:
  enabled: true

supersetWebsockets:
  enabled: true
  image:
    repository: ${IMAGE_REGISTRY}/${WEBSOCKET_REPO}
    tag: "${IMAGE_TAG}"
    pullPolicy: IfNotPresent
  config:
    {
      "port": 8080,
      "logLevel": "info",
      "logToFile": false,
      "logFilename": "app.log",
      "statsd": { "host": "127.0.0.1", "port": 8125, "globalTags": [] },
      "redis": { "port": 6379, "host": "${INFRA_REDIS_SERVICE}", "password": "", "db": 0, "ssl": false },
      "redisStreamPrefix": "async-events-",
      "jwtSecret": "CHANGE-ME",
      "jwtCookieName": "async-token"
    }

init:
  loadExamples: false
  createAdmin: true
  adminUser:
    username: admin
    password: admin

ingress:
  enabled: true
  ingressClassName: nginx
  hosts:
    - superset.example.com
  tls: []

configOverrides:
  secret: |
    SECRET_KEY = os.environ.get("SUPERSET_SECRET_KEY")
  proxy_fix: |
    ENABLE_PROXY_FIX = True
VALUES_EOF

cp "${SCRIPT_DIR}/deploy.env.example" "${BUNDLE_DIR}/deploy.env.example"
cp "${SCRIPT_DIR}/deploy.sh" "${BUNDLE_DIR}/deploy.sh"
cp "${SCRIPT_DIR}/lib.sh" "${BUNDLE_DIR}/lib.sh"
chmod +x "${BUNDLE_DIR}/deploy.sh"

cat > "${BUNDLE_DIR}/bundle.conf" <<EOF
IMAGE_REGISTRY="${IMAGE_REGISTRY}"
IMAGE_REPOSITORY="${IMAGE_REPOSITORY}"
IMAGE_TAG="${IMAGE_TAG}"
SUPERSET_IMAGE="${SUPERSET_IMAGE}"
WEBSOCKET_IMAGE="${WEBSOCKET_IMAGE}"
WEBSOCKET_REPO="${WEBSOCKET_REPO}"
POSTGRES_IMAGE="${POSTGRES_IMAGE}"
POSTGRES_TAG="${POSTGRES_TAG}"
REDIS_IMAGE="${REDIS_IMAGE}"
REDIS_TAG="${REDIS_TAG}"
DOCKERIZE_IMAGE="${DOCKERIZE_IMAGE}"
DOCKERIZE_REPO="${DOCKERIZE_REPO}"
DOCKERIZE_TAG="${DOCKERIZE_TAG}"
NGINX_IMAGE="${NGINX_IMAGE}"
NGINX_TAG="${NGINX_TAG}"
INCLUDE_NGINX="${INCLUDE_NGINX}"
INFRA_POSTGRES_SERVICE="${INFRA_POSTGRES_SERVICE}"
INFRA_REDIS_SERVICE="${INFRA_REDIS_SERVICE}"
HELM_CHART_VERSION="${HELM_CHART_VERSION}"
HELM_NAMESPACE="${HELM_NAMESPACE}"
HELM_RELEASE="${HELM_RELEASE}"
HELM_CHART_PATH="helm/superset"
BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
EOF

cat > "${BUNDLE_DIR}/IMAGES-CHECKLIST.txt" <<EOF
So sánh docker-compose local dev vs K8s bundle
===============================================

LOCAL (docker ps)                    BUNDLE K8s
─────────────────────────────────────────────────────────
superset-superset                    ${SUPERSET_IMAGE}
superset-superset-worker             (cùng image app)
superset-superset-worker-beat        (cùng image app)
superset-superset-websocket          ${WEBSOCKET_IMAGE}
superset-superset-node               KHÔNG CẦN (dev webpack only)
nginx:latest                         ${NGINX_IMAGE} (tuỳ chọn)
postgres:17                          ${POSTGRES_IMAGE}
redis:7                              ${REDIS_IMAGE}
(init: dockerize)                    ${DOCKERIZE_IMAGE}
EOF

cat > "${BUNDLE_DIR}/README.txt" <<EOF
Superset K8s Bundle (full stack)
=================================
Superset app : ${SUPERSET_IMAGE}
WebSocket    : ${WEBSOCKET_IMAGE}
PostgreSQL   : ${POSTGRES_IMAGE}
Redis        : ${REDIS_IMAGE}
Dockerize    : ${DOCKERIZE_IMAGE}
Helm chart   : superset ${HELM_CHART_VERSION}

Xem IMAGES-CHECKLIST.txt để so sánh với docker-compose local dev.

TRÊN MÁY DEPLOY:
  1. Copy cả thư mục này lên máy deploy
  2. ./deploy.sh
     (lần đầu sẽ hỏi tham số; lần sau tự skip image không đổi version)
  3. Chỉ Superset tag đổi → chỉ load/push/deploy lại app
     Infra (postgres/redis/nginx) giữ nguyên version → SKIP

State file: .deploy-state.env (tự tạo sau deploy thành công)
EOF

echo ""
echo "=============================================="
echo " HOÀN TẤT"
echo "=============================================="
echo " Bundle: ${BUNDLE_DIR}"
echo ""
echo " Images:"
ls -lh "${IMAGES_DIR}/"
echo ""
echo " Copy & deploy:"
echo "   scp -r ${BUNDLE_DIR} user@deploy-host:~/"
echo "   ssh user@deploy-host 'cd superset-k8s-bundle-${IMAGE_TAG} && ./deploy.sh'"
echo ""
