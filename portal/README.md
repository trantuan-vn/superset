# Portal Kết xuất — Phase 2

Scaffold + **đăng nhập local/SSO**, session Redis, multi-tenant cho Portal quy trình kết xuất dữ liệu trên Apache Superset.

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

### 2. Đăng nhập demo (local — SSO tắt mặc định)

| Trường | Giá trị |
|---|---|
| Mã doanh nghiệp | `demo-corp` |
| Email | `admin@demo-corp` / `cntt.cv@demo-corp` / `cntt.ld@demo-corp` |
| Mật khẩu | `Pass123!` |

Khi **bật LDAP lần đầu**, nhập **Mật khẩu Portal** trên form (vd. `Pass123!`) — user khớp mật khẩu được đẩy sang LDAP, `password_hash` xóa → chỉ còn LDAP. Admin đăng nhập: `admin` hoặc `admin@demo-corp` + cùng mật khẩu.

Mở http://localhost:3000 → redirect `/login` → sau đăng nhập vào `/dashboard`.

**Tenant admin:** `/admin/settings` — bật SSO, chọn LDAP hoặc OIDC, lưu cấu hình.

### 3. Kiểm tra API

```bash
# Health
curl -f http://localhost:8000/health

# Login options (public)
curl "http://localhost:8000/auth/login-options?tenant_slug=demo-corp"

# Login (lưu cookie session)
curl -c /tmp/portal.cookie -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"tenant_slug":"demo-corp","username":"admin@demo-corp","password":"Pass123!"}'

# Me
curl -b /tmp/portal.cookie http://localhost:8000/auth/me
```

### 4. Test stack LDAP / Keycloak (Gate 2)

```bash
docker compose -f portal/docker/docker-compose.auth-test.yml up -d
```

| Dịch vụ | URL / cổng |
|---|---|
| OpenLDAP | `ldap://localhost:1389` |
| phpLDAPadmin | http://localhost:18081 |
| Keycloak | http://localhost:8082 (admin / admin) |
| Step CA | https://localhost:9443 |

**Lưu ý Docker Desktop (macOS):** Không bind-mount trực tiếp file `bootstrap.ldif` vào image `osixia/openldap` — Docker có thể tạo **thư mục** cùng tên và OpenLDAP sẽ lỗi. Compose hiện dùng service `openldap-bootstrap` seed sau khi LDAP healthy.

Nếu `portal-auth-openldap` đã lỗi trước đó, xóa volume/container cũ rồi chạy lại:

```bash
docker rm -f portal-auth-openldap portal-auth-openldap-bootstrap
# Nếu bootstrap.ldif thành thư mục rỗng (do mount lỗi):
rm -rf portal/docker/auth-test/ldap/bootstrap.ldif
git checkout -- portal/docker/auth-test/ldap/bootstrap.ldif
docker compose -f portal/docker/docker-compose.auth-test.yml up -d
```

**phpLDAPadmin:** http://localhost:18081 (đổi cổng: `PHPLDAPADMIN_PORT=8081 docker compose ... up -d` nếu 18081 bận).

Cấu hình tenant qua UI **Cài đặt xác thực** hoặc PATCH `/tenants/{id}/settings`:

- **T2 LDAP:** `auth_mode=ldap`, URI `ldap://host.docker.internal:1389`, bind DN/password, **Mật khẩu Portal** `Pass123!` khi lưu lần đầu → admin login `admin` / `Pass123!`
- **T3 OIDC:** `auth_mode=oidc`, issuer `http://localhost:8082/realms/demo-corp`, client `portal`, secret trong `OIDC_CLIENT_SECRET`

### 5. Dừng stack

```bash
docker compose -f portal/docker/docker-compose.portal.yml down
```

## Biến môi trường

| Biến | Mặc định | Mô tả |
|---|---|---|
| `DATABASE_URL` | `postgresql://portal:portal@localhost:5433/portal` | PostgreSQL Portal DB |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis session store |
| `SESSION_TTL_HOURS` | `8` | Thời hạn session (giờ) |
| `PORTAL_PUBLIC_BASE_URL` | `http://localhost:8000` | Base URL API (OIDC callback) |
| `FRONTEND_BASE_URL` | `http://localhost:3000` | Redirect sau SSO |
| `LDAP_BIND_PASSWORD` | `admin` | Dev secret cho `secret/portal/ldap-bind` |
| `OIDC_CLIENT_SECRET` | *(Keycloak dev)* | Dev secret cho OIDC client |
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

## Gate 2 — Checklist

- [ ] `GET /auth/login-options` — SSO OFF ẩn nút; SSO ON + OIDC hiện **Đăng nhập SSO**
- [ ] LDAP: bind OpenLDAP → session + audit `AUTH_SSO_LOGIN`
- [ ] OIDC: Keycloak redirect → callback → session
- [ ] `GET/PATCH /tenants/{id}/settings` — tenant_admin, secrets masked
- [ ] Regression T1: local login khi SSO tắt
- [ ] UI: `/admin/settings` form toggle + cấu hình

## Phase tiếp theo

**Phase 3:** Ký số PKI (feature flag) — xem §7 và §12.5 trong spec.
