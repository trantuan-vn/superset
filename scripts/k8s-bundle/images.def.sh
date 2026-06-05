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

# Đồng bộ với docker-compose.yml (local dev)
#
# Local dev container          → K8s production mapping
# ─────────────────────────────────────────────────────
# superset-superset            → 1 image (app) — Helm supersetNode
# superset-superset-worker     → cùng image app — Helm supersetWorker
# superset-superset-worker-beat→ cùng image app — Helm supersetCeleryBeat
# superset-superset-websocket  → image riêng — Helm supersetWebsockets
# superset-superset-node       → KHÔNG CẦN prod (webpack dev only)
# nginx:latest                 → infra nginx (tuỳ chọn)
# postgres:17                  → infra postgres
# redis:7                      → infra redis
# apache/superset:dockerize    → init container

DOCKERIZE_SOURCE="apache/superset:dockerize"
DOCKERIZE_REPO="superset-dockerize"
DOCKERIZE_TAG="dockerize"

POSTGRES_SOURCE="postgres:17"
POSTGRES_REPO="postgres"
POSTGRES_TAG="17"

REDIS_SOURCE="redis:7"
REDIS_REPO="redis"
REDIS_TAG="7"

NGINX_SOURCE="nginx:latest"
NGINX_REPO="nginx"
NGINX_TAG="latest"

WEBSOCKET_REPO="superset-websocket"
# Tag websocket theo cùng IMAGE_TAG của app

HELM_CHART_VERSION="0.15.5"

# Tên Service K8s cho infra (khớp helm values connections)
INFRA_POSTGRES_SERVICE="superset-postgres"
INFRA_REDIS_SERVICE="superset-redis"
