# Portal Kết xuất — Phase 0

Scaffold cho Portal quy trình kết xuất dữ liệu trên Apache Superset. Phase 0 gồm backend health check, migration baseline (`tenants`, `tenant_settings`), design tokens và App Shell — **chưa có login**.

Đặc tả đầy đủ: [`docs/portal/SPEC-PORTAL-v1.md`](../docs/portal/SPEC-PORTAL-v1.md)

## Yêu cầu

- Docker 24+ và Docker Compose v2
- (Tùy chọn) Node.js 20+ và Python 3.11+ cho dev ngoài Docker

## Quick start (< 15 phút)

### 1. Khởi động stack

Từ **root repo**:

```bash
docker compose -f portal/docker/docker-compose.portal.yml up -d --build
```

### 2. Kiểm tra

```bash
# Backend health
curl -f http://localhost:8000/health

# Migration đã chạy (trong container portal-api)
docker compose -f portal/docker/docker-compose.portal.yml exec portal-api alembic current
```

Mở trình duyệt:

| URL | Mô tả |
|---|---|
| http://localhost:3000 | App shell (trang chủ) |
| http://localhost:3000/health-ui | Health UI — gọi `/health` qua proxy nginx |
| http://localhost:8000/docs | OpenAPI (FastAPI) |

### 3. Dừng stack

```bash
docker compose -f portal/docker/docker-compose.portal.yml down
```

Giữ dữ liệu DB: bỏ `-v`. Xóa volume: `docker compose ... down -v`.

## Biến môi trường

| Biến | Mặc định | Mô tả |
|---|---|---|
| `DATABASE_URL` | `postgresql://portal:portal@localhost:5433/portal` | PostgreSQL Portal DB |
| `APP_NAME` | `Portal Kết xuất` | Tên hiển thị API health |
| `APP_ENV` | `development` | Môi trường (`development` / `staging` / `production`) |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | Origins được phép gọi API |
| `VITE_API_URL` | *(trống trong Docker)* | Base URL API cho frontend dev/build |

Mẫu file: [`portal/.env.example`](.env.example)

## Dev local (không Docker)

### Backend

```bash
cd portal/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
# Cần PostgreSQL chạy (vd. chỉ portal-db từ compose)
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd portal/frontend
npm install
echo 'VITE_API_URL=http://localhost:8000' > .env.local
npm run dev
# http://localhost:5173
```

### Tests backend

```bash
cd portal/backend
pytest tests/
```

### Lint frontend

```bash
cd portal/frontend
npm run lint && npm run typecheck
```

## Cấu trúc thư mục

```
portal/
├── backend/          # FastAPI + Alembic
├── frontend/         # React 18 + Vite + Ant Design 5
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.portal.yml
│   └── docker-compose.auth-test.yml   # Phase 2–3 (LDAP/PKI test)
└── k8s/helm/portal/  # Helm chart — Phase 12
```

## Gate 0 — Checklist

- [ ] `docker compose -f portal/docker/docker-compose.portal.yml up` thành công
- [ ] `GET /health` → 200, `database: connected`
- [ ] `alembic current` → `0001_baseline`
- [ ] UI: sidebar collapse, responsive ≥1280px / ≥768px (drawer mobile)
- [ ] `/health-ui` hiển thị trạng thái API
- [ ] ESLint + TypeScript strict pass (`npm run lint`, `npm run typecheck`)

## Phase tiếp theo

**Phase 1:** Login local, Redis session, `users` table, trang đăng nhập — xem §7 trong spec.
