# Portal Kết xuất — Phase 1

Scaffold + **đăng nhập local**, session Redis, multi-tenant cho Portal quy trình kết xuất dữ liệu trên Apache Superset.

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

### 2. Đăng nhập demo

| Trường | Giá trị |
|---|---|
| Mã doanh nghiệp | `demo-corp` |
| Email | `admin@demo-corp` / `cntt.cv@demo-corp` / `cntt.ld@demo-corp` |
| Mật khẩu | `Pass123!` |

Mở http://localhost:3000 → redirect `/login` → sau đăng nhập vào `/dashboard`.

### 3. Kiểm tra API

```bash
# Health
curl -f http://localhost:8000/health

# Login (lưu cookie session)
curl -c /tmp/portal.cookie -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"tenant_slug":"demo-corp","username":"admin@demo-corp","password":"Pass123!"}'

# Me
curl -b /tmp/portal.cookie http://localhost:8000/auth/me
```

### 4. Dừng stack

```bash
docker compose -f portal/docker/docker-compose.portal.yml down
```

## Biến môi trường

| Biến | Mặc định | Mô tả |
|---|---|---|
| `DATABASE_URL` | `postgresql://portal:portal@localhost:5433/portal` | PostgreSQL Portal DB |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis session store |
| `SESSION_TTL_HOURS` | `8` | Thời hạn session (giờ) |
| `MAX_LOGIN_ATTEMPTS` | `5` | Khóa tài khoản sau N lần sai |
| `SESSION_COOKIE_SECURE` | `false` | Bật `true` trên production HTTPS |
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
# Cần PostgreSQL + Redis (vd. chỉ portal-db, portal-redis từ compose)
alembic upgrade head
python -m app.seed
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
├── backend/          # FastAPI + Alembic + Redis session
├── frontend/         # React 18 + Vite + Ant Design 5
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.portal.yml
│   └── docker-compose.auth-test.yml   # Phase 2–3 (LDAP/PKI test)
└── k8s/helm/portal/  # Helm chart — Phase 12
```

## Gate 1 — Checklist

- [ ] `POST /auth/login` + `GET /auth/me` + `POST /auth/logout` OK
- [ ] Session cookie HttpOnly; tenant isolation (user chỉ thuộc 1 tenant)
- [ ] Khóa tài khoản sau 5 lần đăng nhập sai
- [ ] UI: trang login split layout, validation inline, loading state
- [ ] UI: dashboard welcome + stats placeholder, menu theo `system_role`
- [ ] UI: user menu đăng xuất, tenant badge trên header
- [ ] Session hết hạn → redirect login + toast

## Phase tiếp theo

**Phase 2:** SSO/LDAP (feature flag) — xem §7 và §12 trong spec.
