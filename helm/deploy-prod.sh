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

# ---------------------------------------------------------------------------
# Configure these variables for your environment
# ---------------------------------------------------------------------------
REGISTRY="${REGISTRY:-docker.io/tuantahp}"
TAG="${TAG:-1.0.0}"
NAMESPACE="${NAMESPACE:-superset}"
RELEASE="${RELEASE:-superset}"
# Set USE_TWO_STEP_BUILD=true to use Dockerfile.prod instead of --target prod
USE_TWO_STEP_BUILD="${USE_TWO_STEP_BUILD:-false}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${REGISTRY}/superset:${TAG}"

if [[ "${USE_TWO_STEP_BUILD}" == "true" ]]; then
  echo "==> [two-step] Building lean base from local source..."
  docker build --target lean \
    --build-arg DEV_MODE=false \
    -t superset-base:local \
    "${ROOT}"

  echo "==> [two-step] Building production image (Dockerfile.prod → superset-base:local)..."
  docker build -f "${ROOT}/Dockerfile.prod" \
    --build-arg BASE_IMAGE=superset-base:local \
    -t "${IMAGE}" \
    "${ROOT}"
else
  echo "==> [one-step] Building prod image from local source (--target prod)..."
  docker build --target prod \
    --build-arg DEV_MODE=false \
    -t "${IMAGE}" \
    "${ROOT}"
fi

echo "==> Pushing image..."
docker push "${IMAGE}"

echo "==> Deploying with Helm..."
helm repo add superset https://apache.github.io/superset 2>/dev/null || true
helm repo update

helm upgrade --install "${RELEASE}" superset/superset \
  -f "${ROOT}/helm/my-values.prod.yaml" \
  --set "image.repository=${REGISTRY}/superset" \
  --set "image.tag=${TAG}" \
  -n "${NAMESPACE}" \
  --create-namespace

echo "==> Done. Check rollout:"
echo "    kubectl get pods -n ${NAMESPACE}"
echo "    kubectl logs -n ${NAMESPACE} -l app=superset --tail=30"
