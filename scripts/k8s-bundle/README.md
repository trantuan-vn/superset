# Hướng dẫn deploy Superset lên Kubernetes (offline bundle)

Tài liệu này mô tả quy trình **đóng gói toàn bộ image + Helm chart** trên máy dev, copy sang máy deploy (có thể **không có internet**), rồi triển khai lên Kubernetes bằng một lệnh.

Phù hợp khi:

- Cluster production **không pull được** image từ Docker Hub / internet
- Muốn **một gói portable** (USB, SCP, artifact server) chứa đủ stack
- Đã chỉnh sửa code Superset local và cần deploy **đúng bản build từ repo**

> **Deploy online** (build → push registry → helm trực tiếp): xem [`helm/README-K8S-PRODUCTION.md`](../../helm/README-K8S-PRODUCTION.md).

---

## Tổng quan quy trình

```
┌─────────────────────┐     copy/scp      ┌─────────────────────┐
│  Máy BUILD (dev)    │ ────────────────► │  Máy DEPLOY (K8s)   │
│  ./build-bundle.sh  │                   │  ./deploy.sh        │
└─────────────────────┘                   └─────────────────────┘
         │                                           │
         ▼                                           ▼
  dist/superset-k8s-bundle-<TAG>/            kubectl + helm upgrade
  ├── images/*.tar
  ├── helm/ (chart offline)
  ├── infra/ (postgres, redis)
  └── deploy.sh
```

---

## So sánh `docker compose` local vs K8s bundle

| Container local (`docker ps`) | Image | Trong bundle? | Ghi chú |
|-------------------------------|-------|:-------------:|---------|
| `superset-superset` | `superset-superset` | ✅ | Image app chính |
| `superset-superset-worker` | `superset-superset-worker` | ✅ | **Cùng image app** (Helm worker) |
| `superset-superset-worker-beat` | `superset-superset-worker-beat` | ✅ | **Cùng image app** (Helm celery beat) |
| `superset-superset-websocket` | `superset-superset-websocket` | ✅ | Image riêng, build từ `superset-websocket/` |
| `superset-db` | `postgres:17` | ✅ | Manifest `infra/postgres.yaml` |
| `superset-redis` | `redis:7` | ✅ | Manifest `infra/redis.yaml` |
| `superset-nginx` | `nginx:latest` | ⚙️ tuỳ chọn | K8s thường dùng Ingress thay container nginx |
| `superset-superset-node` | `superset-superset-node` | ❌ | **Chỉ dev** — webpack hot reload; prod bake frontend vào image app |
| *(init)* | `apache/superset:dockerize` | ✅ | Init container chờ DB sẵn sàng |

Sau khi build, file `IMAGES-CHECKLIST.txt` trong bundle liệt kê lại bảng trên.

---

## Kiến trúc trên Kubernetes

```
                    ┌─────────────────────────┐
                    │  Ingress                │
                    │  (INGRESS_HOST)         │
                    └───────────┬─────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
  superset-node×N         superset-worker×N      superset-celery-beat
  (image app)             (image app)            (image app)
        │                       │
        └───────────┬───────────┘
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
  superset-postgres         superset-redis          superset-websocket
  (postgres:17)             (redis:7)               (image websocket)
```

PostgreSQL và Redis dùng **official images** (`postgres:17`, `redis:7`) — khớp `docker-compose.yml` local, **không** dùng Bitnami subchart của Helm.

---

## Yêu cầu

### Máy BUILD (có internet, có source code)

| Công cụ | Mục đích |
|---------|----------|
| Docker | Build image app + websocket, export `.tar` |
| Helm 3.x | Tải chart Superset + dependencies (lần build) |
| Git repo Superset | Source đã chỉnh sửa |

### Máy DEPLOY (cluster K8s)

| Công cụ | Mục đích |
|---------|----------|
| Docker | `docker load` / `docker push` image |
| `kubectl` | Apply infra, kiểm tra pods |
| Helm 3.x | `helm upgrade --install` |
| Quyền push registry | Mặc định `docker.io/tuantahp` (hoặc registry nội bộ) |
| Ingress controller | Expose Superset ra ngoài (nginx-ingress, …) |

---

## Bước 1 — Build bundle (máy dev)

```bash
cd /path/to/superset
./scripts/k8s-bundle/build-bundle.sh
```

Script sẽ hỏi interactive:

| Tham số | Mặc định | Ý nghĩa |
|---------|----------|---------|
| Docker registry | `docker.io/tuantahp` | Registry đích trên máy deploy |
| Image tag | `1.0.0` | **Tăng tag mỗi khi có code mới** |
| Thư mục output | `dist/` | Nơi tạo bundle |
| K8s namespace | `superset` | Namespace deploy |
| Helm release | `superset` | Tên release Helm |
| Đóng gói nginx? | `yes` | Image `nginx:latest` (tuỳ chọn) |

### Script thực hiện 6 bước

1. Build image Superset `--target prod` (app + worker + beat dùng chung)
2. Build image WebSocket từ `superset-websocket/`
3. Export `superset-*.tar`, `websocket-*.tar`
4. Pull & export `postgres:17`, `redis:7`, `dockerize`, `nginx` (nếu chọn)
5. Tải Helm chart Superset + dependencies (offline trong bundle)
6. Tạo `helm/values.yaml`, `infra/`, `deploy.sh`, `bundle.conf`

### Output

```
dist/superset-k8s-bundle-1.0.0/
├── images/
│   ├── superset-1.0.0.tar
│   ├── websocket-1.0.0.tar
│   ├── postgres-17.tar
│   ├── redis-7.tar
│   ├── dockerize-dockerize.tar
│   └── nginx-latest.tar          # nếu chọn đóng gói nginx
├── images.manifest
├── infra/
│   ├── postgres.yaml
│   └── redis.yaml
├── helm/
│   ├── superset/                 # chart + deps (offline)
│   └── values.yaml
├── deploy.sh
├── deploy.env.example
├── lib.sh
├── bundle.conf
├── IMAGES-CHECKLIST.txt
└── README.txt
```

Thời gian build: ~15–30 phút (tuỳ CPU và lần đầu pull base image).

---

## Bước 2 — Copy bundle sang máy deploy

```bash
# Ví dụ SCP
scp -r dist/superset-k8s-bundle-1.0.0 user@deploy-host:~/

# Hoặc nén rồi copy (bundle có thể vài GB)
tar czf superset-k8s-bundle-1.0.0.tar.gz -C dist superset-k8s-bundle-1.0.0
scp superset-k8s-bundle-1.0.0.tar.gz user@deploy-host:~/
ssh user@deploy-host 'tar xzf superset-k8s-bundle-1.0.0.tar.gz'
```

---

## Bước 3 — Deploy lên Kubernetes (máy deploy)

```bash
cd ~/superset-k8s-bundle-1.0.0

# Đăng nhập registry (nếu push image)
docker login

# Cấu hình kubectl trỏ đúng cluster
kubectl config current-context

# Deploy
./deploy.sh
```

**Lần đầu**, `deploy.sh` hỏi interactive và tạo `deploy.env`:

| Biến | Mô tả |
|------|--------|
| `SUPERSET_SECRET_KEY` | Bắt buộc — tạo bằng `openssl rand -base64 42` |
| `ADMIN_PASSWORD` | Mật khẩu user `admin` |
| `INGRESS_HOST` | Domain truy cập Superset |
| `INGRESS_CLASS` | Mặc định `nginx` |
| `HELM_NAMESPACE` | Mặc định `superset` |
| `SKIP_DOCKER_PUSH` | `true` nếu cluster dùng image local, không cần push |
| `FORCE_HELM_UPGRADE` | `true` để bắt buộc helm upgrade |

Hoặc tạo `deploy.env` trước:

```bash
cp deploy.env.example deploy.env
# Sửa SUPERSET_SECRET_KEY, INGRESS_HOST, ...
./deploy.sh
```

### `deploy.sh` làm gì?

1. **Load & push images** — skip nếu version không đổi (xem mục Smart skip)
2. **Kiểm tra thay đổi version** — quyết định có cần deploy không
3. **Apply infra** — `kubectl apply -f infra/` (postgres + redis) khi cần
4. **Helm upgrade** — chart offline trong bundle, không cần internet

### Kiểm tra sau deploy

```bash
kubectl get pods -n superset
kubectl get ingress -n superset

# Truy cập tạm qua port-forward
kubectl port-forward -n superset svc/superset 8088:8088
# Mở http://localhost:8088
```

---

## Smart skip — chỉ deploy khi version đổi

File `.deploy-state.env` (tự tạo sau deploy thành công) lưu version image đã deploy.

| Tình huống | Hành vi |
|------------|---------|
| Chạy lại `./deploy.sh`, mọi version giống cũ | **Skip** load/push/helm |
| Chỉ đổi `IMAGE_TAG` Superset (code mới) | Load/push app + websocket, **helm upgrade**; postgres/redis **giữ nguyên** |
| Đổi `postgres:17` → `postgres:18` trong `images.def.sh` | Load/push postgres, **apply infra**, helm upgrade |
| Muốn deploy lại dù version không đổi | `FORCE_HELM_UPGRADE=true ./deploy.sh` |

---

## Upgrade khi có code mới

```bash
# Trên máy BUILD
./scripts/k8s-bundle/build-bundle.sh
# Đổi IMAGE_TAG: 1.0.0 → 1.0.1

# Copy bundle mới sang máy deploy
scp -r dist/superset-k8s-bundle-1.0.1 user@deploy-host:~/

# Trên máy DEPLOY
cd ~/superset-k8s-bundle-1.0.1
./deploy.sh
# Chỉ xử lý image app/websocket mới; infra skip nếu version không đổi
```

---

## Tùy chỉnh image versions

Sửa [`images.def.sh`](images.def.sh) trước khi chạy `build-bundle.sh`:

```bash
POSTGRES_SOURCE="postgres:17"    # khớp docker-compose
REDIS_SOURCE="redis:7"
NGINX_SOURCE="nginx:latest"
DOCKERIZE_SOURCE="apache/superset:dockerize"
HELM_CHART_VERSION="0.15.5"
```

Registry mặc định: `docker.io/tuantahp`. Đổi khi chạy `build-bundle.sh` (prompt interactive).

---

## File trong thư mục `scripts/k8s-bundle/`

| File | Mô tả |
|------|--------|
| [`build-bundle.sh`](build-bundle.sh) | Build image, export tar, đóng gói Helm chart offline |
| [`deploy.sh`](deploy.sh) | Load/push image, apply infra, helm upgrade (smart skip) |
| [`images.def.sh`](images.def.sh) | Định nghĩa version image infra (postgres, redis, nginx, …) |
| [`lib.sh`](lib.sh) | Helper: state file, load/push, version compare |
| [`deploy.env.example`](deploy.env.example) | Mẫu cấu hình deploy |

---

## Xử lý sự cố

### `docker load` / `docker push` lỗi

```bash
docker login                    # đăng nhập registry
docker images | grep tuantahp   # kiểm tra image đã load
```

### Pod `Init:CrashLoopBackOff` (chờ DB)

Postgres chưa sẵn sàng. Kiểm tra:

```bash
kubectl get pods -n superset
kubectl logs -n superset statefulset/superset-postgres
kubectl get svc -n superset | grep postgres
```

### Pod `ImagePullBackOff`

Cluster không pull được image. Đảm bảo:

- Đã `docker push` thành công (hoặc `SKIP_DOCKER_PUSH=true` + image có trên node)
- Registry credentials đúng (`imagePullSecrets` nếu registry private)

### Helm upgrade lỗi chart dependency

Bundle đã chứa chart offline. Không chạy `helm repo update` trên máy deploy — dùng chart trong `helm/superset/`.

### WebSocket không kết nối

Kiểm tra pod websocket và Redis:

```bash
kubectl get pods -n superset -l app.kubernetes.io/name=superset-websocket
kubectl logs -n superset -l app.kubernetes.io/name=superset-websocket
```

### Muốn dùng PostgreSQL/Redis managed (RDS, ElastiCache)

1. Deploy bundle **không** apply `infra/` (hoặc xóa `infra/` khỏi bundle)
2. Sửa `helm/values.yaml` trong bundle: set `db_host`, `redis_host` trỏ external
3. Set `postgresql.enabled=false`, `redis.enabled=false` (mặc định bundle đã tắt Bitnami)

Chi tiết values production: [`helm/my-values.prod.yaml`](../../helm/my-values.prod.yaml).

---

## Checklist nhanh

**Máy build**

- [ ] Code đã test local (`docker compose up`, truy cập `:9000` hoặc `:8088`)
- [ ] Chạy `./scripts/k8s-bundle/build-bundle.sh`
- [ ] Kiểm tra `dist/superset-k8s-bundle-<TAG>/images/` đủ file `.tar`
- [ ] Copy bundle sang máy deploy

**Máy deploy**

- [ ] `docker login`, `kubectl` đúng cluster
- [ ] `./deploy.sh` — nhập `SUPERSET_SECRET_KEY`, `INGRESS_HOST`
- [ ] `kubectl get pods -n superset` — tất cả Running
- [ ] Truy cập qua Ingress hoặc port-forward

---

## Liên quan

| Tài liệu | Nội dung |
|----------|----------|
| [`helm/README-K8S-PRODUCTION.md`](../../helm/README-K8S-PRODUCTION.md) | Deploy online: build → push → helm (không bundle) |
| [`helm/my-values.prod.yaml`](../../helm/my-values.prod.yaml) | Helm values production (DB external, ingress, resources) |
| [`helm/deploy-prod.sh`](../../helm/deploy-prod.sh) | Script deploy online một bước |
| [`Dockerfile`](../../Dockerfile) | Target `prod` — image app chính |
| [`superset-websocket/Dockerfile`](../../superset-websocket/Dockerfile) | Image WebSocket |
