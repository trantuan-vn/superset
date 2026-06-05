# Hướng dẫn deploy Apache Superset lên Kubernetes Production

Tài liệu này mô tả quy trình triển khai Superset **có chỉnh sửa code local** (`superset/`, `superset-frontend/`) lên cluster Kubernetes production bằng **Docker** + **Helm**.

## Tổng quan

| Môi trường | Cách chạy | Frontend |
|------------|-----------|----------|
| **Local dev** | `docker compose up` | Webpack dev server, hot reload (`:9000`) |
| **Production K8s** | Helm chart | Frontend **build sẵn** trong Docker image |

**Không** dùng `docker-compose.yml` cho production. **Không** dùng image `apache/superset:latest` nếu bạn đã sửa code — phải build image từ repo này.

### Kiến trúc production (mẫu)

```
                    ┌─────────────────────────┐
                    │  Ingress (HTTPS)        │
                    │  superset.your-co.com   │
                    └───────────┬─────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
        superset-node×N    superset-worker×N   celery-beat
              │                 │
              └────────┬────────┘
                       ▼
         ┌─────────────────────────────┐
         │  PostgreSQL (external)      │  ← metadata DB
         │  Redis (external)           │  ← cache + Celery
         └─────────────────────────────┘
```

Image production: `docker.io/tuantahp/superset:<TAG>`

---

## Yêu cầu

### Công cụ trên máy build/deploy

- Docker (build multi-stage)
- `kubectl` (đã cấu hình context trỏ đúng cluster)
- Helm 3.x
- Tài khoản Docker Hub (`docker login`) nếu push lên `docker.io/tuantahp`

### Hạ tầng Kubernetes

- Cluster K8s đang chạy (EKS, GKE, AKS, on-prem, …)
- **PostgreSQL** managed (RDS, Cloud SQL, …) — metadata database
- **Redis** managed (ElastiCache, Memorystore, …) — cache + message broker
- **Ingress controller** (nginx-ingress, Traefik, …) nếu expose qua domain
- (Tuỳ chọn) cert-manager hoặc TLS secret cho HTTPS

### Tài nguyên khuyến nghị (tối thiểu)

| Component | Replicas | CPU / Memory |
|-----------|----------|--------------|
| superset-node | 2 | 500m / 1Gi |
| superset-worker | 2 | 500m / 1Gi |
| celery-beat | 1 | 250m / 512Mi |

---

## File liên quan trong repo

| File | Mô tả |
|------|--------|
| `Dockerfile` | Target `prod`: build lean + drivers từ source |
| `Dockerfile.prod` | Layer drivers trên `superset-base:local` (build 2 bước) |
| `helm/my-values.prod.yaml` | Helm values production (DB, Ingress, secrets) |
| `helm/deploy-prod.sh` | Script tự động: build → push → helm upgrade |

---

## Bước 1 — Phát triển & kiểm tra local

```bash
cd /path/to/superset

# Khởi động môi trường dev
docker compose up --build

# Truy cập UI dev (hot reload frontend)
open http://localhost:9000

# Đăng nhập mặc định
# user: admin / password: admin
```

Sau khi sửa code:

- **Python** (`superset/`): Flask tự reload trong container
- **Frontend** (`superset-frontend/`): save file → refresh `http://localhost:9000`

Chạy kiểm tra chất lượng trước khi build production:

```bash
source .venv/bin/activate   # nếu có venv local
pre-commit run
```

---

## Bước 2 — Cấu hình Helm values

Mở `helm/my-values.prod.yaml` và thay **tất cả** giá trị `CHANGE_ME`:

### 2.1 Image

```yaml
image:
  repository: docker.io/tuantahp/superset
  tag: "1.0.0"    # đổi mỗi lần release
```

### 2.2 Secret key (bắt buộc)

```bash
openssl rand -base64 42
```

```yaml
extraSecretEnv:
  SUPERSET_SECRET_KEY: "<kết-quả-lệnh-trên>"
```

> Không commit secret thật vào git. Dùng Sealed Secrets, External Secrets Operator, hoặc inject qua CI/CD.

### 2.3 PostgreSQL & Redis (external)

Tắt subchart bundled, trỏ host thật:

```yaml
postgresql:
  enabled: false

redis:
  enabled: false

supersetNode:
  connections:
    db_host: "postgres.internal.your-company.com"
    db_port: "5432"
    db_user: superset
    db_pass: "CHANGE_ME-db-password"
    db_name: superset

    redis_host: "redis.internal.your-company.com"
    redis_port: "6379"
```

### 2.4 Admin user (lần cài đầu)

```yaml
init:
  loadExamples: false
  createAdmin: true
  adminUser:
    username: admin
    email: admin@your-company.com
    password: "CHANGE_ME-admin-password"
```

### 2.5 Ingress

```yaml
ingress:
  enabled: true
  ingressClassName: nginx
  hosts:
    - superset.your-company.com
  tls:
    - secretName: superset-tls
      hosts:
        - superset.your-company.com
```

### 2.6 Registry private (nếu cần)

```yaml
imagePullSecrets:
  - name: regcred
```

Tạo secret pull image:

```bash
kubectl create secret docker-registry regcred \
  --docker-server=docker.io \
  --docker-username=tuantahp \
  --docker-password=<token> \
  -n superset
```

---

## Bước 3 — Build Docker image production

Frontend **phải** được compile trong image (`DEV_MODE=false`).

### Cách A — Một lệnh (khuyến nghị)

Build target `prod` trong `Dockerfile` gốc (lean + drivers):

```bash
export TAG=1.0.0

docker build --target prod \
  --build-arg DEV_MODE=false \
  -t docker.io/tuantahp/superset:${TAG} \
  .
```

### Cách B — Hai bước (tùy chỉnh drivers trong `Dockerfile.prod`)

```bash
export TAG=1.0.0

# Bước 1: lean base từ source local
docker build --target lean \
  --build-arg DEV_MODE=false \
  -t superset-base:local .

# Bước 2: thêm drivers
docker build -f Dockerfile.prod \
  --build-arg BASE_IMAGE=superset-base:local \
  -t docker.io/tuantahp/superset:${TAG} .
```

> `Dockerfile.prod` mặc định `BASE_IMAGE=superset-base:local` — **không** dùng `apache/superset:latest` khi có code custom.

### Cách C — Script tự động

```bash
export TAG=1.0.0
export REGISTRY=docker.io/tuantahp

# Build 1 bước (mặc định)
./helm/deploy-prod.sh

# Hoặc build 2 bước qua Dockerfile.prod
USE_TWO_STEP_BUILD=true ./helm/deploy-prod.sh
```

Script sẽ: build → `docker push` → `helm upgrade --install`.

---

## Bước 4 — Push image lên Docker Hub

```bash
docker login

export TAG=1.0.0
docker push docker.io/tuantahp/superset:${TAG}
```

Kiểm tra image tồn tại:

```bash
docker pull docker.io/tuantahp/superset:1.0.0
```

---

## Bước 5 — Deploy lên Kubernetes

### 5.1 Thêm Helm repo

```bash
helm repo add superset https://apache.github.io/superset
helm repo update
```

### 5.2 Cài đặt / nâng cấp

```bash
export TAG=1.0.0

helm upgrade --install superset superset/superset \
  -f helm/my-values.prod.yaml \
  --set image.repository=docker.io/tuantahp/superset \
  --set image.tag=${TAG} \
  -n superset \
  --create-namespace
```

Helm sẽ tạo:

- Deployment `superset` (web)
- Deployment `superset-worker` (Celery)
- Deployment `superset-celerybeat` (nếu bật)
- Job `superset-init-db` (migration + admin user)

---

## Bước 6 — Kiểm tra sau deploy

### 6.1 Trạng thái pods

```bash
kubectl get pods -n superset -w
```

Kỳ vọng tất cả `Running`, init job `Completed`:

```
NAME                              READY   STATUS      RESTARTS   AGE
superset-xxxx                     1/1     Running     0          2m
superset-worker-xxxx              1/1     Running     0          2m
superset-celerybeat-xxxx          1/1     Running     0          2m
superset-init-db-xxxx             0/1     Completed   0          3m
```

### 6.2 Log init job (migration)

```bash
kubectl logs -n superset job/superset-init-db
```

Phải thấy `superset db upgrade` thành công.

### 6.3 Log web app

```bash
kubectl logs -n superset -l app=superset --tail=50
```

### 6.4 Health check

```bash
kubectl port-forward -n superset svc/superset 8088:8088
curl -f http://localhost:8088/health
```

### 6.5 Truy cập UI

- Qua Ingress: `https://superset.your-company.com`
- Hoặc port-forward: `kubectl port-forward -n superset svc/superset 8088:8088` → `http://localhost:8088`

Đăng nhập bằng user đã cấu hình trong `init.adminUser`.

---

## Bước 7 — Release phiên bản mới (có sửa code)

Quy trình mỗi lần có thay đổi code:

```bash
# 1. Test local
docker compose up
pre-commit run

# 2. Tăng tag version
export TAG=1.0.1

# 3. Build & push
docker build --target prod --build-arg DEV_MODE=false \
  -t docker.io/tuantahp/superset:${TAG} .
docker push docker.io/tuantahp/superset:${TAG}

# 4. Cập nhật tag trong my-values.prod.yaml (hoặc --set)
helm upgrade --install superset superset/superset \
  -f helm/my-values.prod.yaml \
  --set image.tag=${TAG} \
  -n superset

# 5. Theo dõi rollout
kubectl rollout status deployment/superset -n superset
kubectl rollout status deployment/superset-worker -n superset
```

Init job `post-upgrade` tự chạy `superset db upgrade` khi có migration mới.

---

## Rollback

### Rollback Helm

```bash
helm history superset -n superset
helm rollback superset <REVISION> -n superset
```

### Rollback image tag

```bash
helm upgrade --install superset superset/superset \
  -f helm/my-values.prod.yaml \
  --set image.tag=1.0.0 \
  -n superset
```

---

## Xử lý sự cố

| Triệu chứng | Nguyên nhân thường gặp | Cách xử lý |
|-------------|------------------------|------------|
| `ImagePullBackOff` | Sai tag hoặc chưa push image | `docker push docker.io/tuantahp/superset:TAG` |
| `CrashLoopBackOff` init | DB/Redis không kết nối được | Kiểm tra `db_host`, `redis_host`, firewall, security group |
| Init job failed | Migration lỗi | `kubectl logs job/superset-init-db -n superset` |
| UI trắng / lỗi JS | Dùng image upstream thay vì build local | Build lại với `--target prod` từ repo |
| 502 từ Ingress | Pod chưa ready | `kubectl describe pod -n superset` |
| Login không được | Sai admin password | Reset qua init job hoặc `superset fab create-admin` trong pod |

### Debug trong pod

```bash
kubectl exec -it -n superset deploy/superset -- bash
# Trong pod:
curl localhost:8088/health
```

---

## Checklist bảo mật production

- [ ] Đổi `SUPERSET_SECRET_KEY` (không dùng giá trị mẫu)
- [ ] Đổi mật khẩu Postgres, Redis, admin user
- [ ] `init.loadExamples: false`
- [ ] `postgresql.enabled: false` — dùng DB managed có backup
- [ ] Bật TLS trên Ingress
- [ ] `runAsUser: 1000` (không chạy root)
- [ ] Không commit secrets vào git
- [ ] Test migration trên staging trước production
- [ ] Giới hạn network: chỉ Superset pods được kết nối Postgres/Redis

---

## Tham khảo

- [Superset — Kubernetes (official)](https://superset.apache.org/docs/installation/kubernetes)
- [Superset — Docker builds](https://superset.apache.org/docs/installation/docker-builds)
- Helm chart gốc: `helm/superset/` trong repo Apache Superset
- Local dev: `docs/developer_docs/contributing/development-setup.md`

---

## Tóm tắt lệnh nhanh

```bash
# Cấu hình
vim helm/my-values.prod.yaml   # đổi CHANGE_ME

# Build + push + deploy (all-in-one)
export TAG=1.0.0
./helm/deploy-prod.sh

# Kiểm tra
kubectl get pods -n superset
kubectl port-forward -n superset svc/superset 8088:8088
curl http://localhost:8088/health
```
