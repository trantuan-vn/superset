# Spec Portal Kết xuất Dữ liệu v1.2

> **Mục đích:** Đặc tả triển khai **tuần tự, có Gate kiểm duyệt** cho Portal quy trình kết xuất trên Apache Superset.  
> **Nguyên tắc:** Mỗi Phase = **Backend + Frontend + Gate** → OK mới sang Phase tiếp theo.  
> **Trạng thái:** Draft v1.2 — UI/UX enterprise (§14), auth test (§12), K8s LDAP/PKI (§13).

### Cách đọc tài liệu

| Bạn cần | Đọc |
|---|---|
| Bắt đầu triển khai | §3 bảng tóm tắt → §7 Phase 0 |
| Thiết kế giao diện | §14 (bắt buộc từ Phase 0) |
| Schema DB | §5 |
| Test LDAP/PKI local | §12 |
| Production K8s | §13 |
| API endpoints | §8 |

### Quy ước Phase

Mỗi Phase gồm 4 khối cố định:

1. **Mục tiêu** — một câu outcome  
2. **Phạm vi** — Backend · Frontend · Schema (chỉ liệt kê delta)  
3. **Deliverables** — checkbox bắt buộc  
4. **Gate** — tiêu chí nghiệm thu (Backend + UI + Security)

---

## Mục lục

1. [Tổng quan kiến trúc](#1-tổng-quan-kiến-trúc)
2. [Ma trận quyết định đã chốt](#2-ma-trận-quyết-định-đã-chốt)
3. [Sơ đồ Phase nối tiếp](#3-sơ-đồ-phase-nối-tiếp)
4. [Cấu trúc repo & hạ tầng](#4-cấu-trúc-repo--hạ-tầng)
5. [ERD & Schema dữ liệu Portal](#5-erd--schema-dữ-liệu-portal)
6. [Role Blueprint Superset](#6-role-blueprint-superset)
7. [Chi tiết từng Phase](#7-chi-tiết-từng-phase)
8. [API Reference (tổng hợp)](#8-api-reference-tổng-hợp)
9. [Cấu hình Superset theo Phase](#9-cấu-hình-superset-theo-phase)
10. [Checklist kiểm duyệt chung](#10-checklist-kiểm-duyệt-chung)
11. [Phụ lục](#11-phụ-lục)
12. [Docker images test LDAP & Ký số (dev/staging)](#12-docker-images-test-ldap--ký-số-devstaging)
13. [Triển khai K8s Production — LDAP & Ký số](#13-triển-khai-k8s-production--ldap--ký-số)
14. [Hệ thống thiết kế giao diện (UI/UX)](#14-hệ-thống-thiết-kế-giao-diện-uiux)

---

## 1. Tổng quan kiến trúc

### 1.1. Mô hình Lựa chọn 3

| Thành phần | Trách nhiệm |
|---|---|
| **Portal** | IAM (login), workflow duyệt, multi-tenant, AI orchestrator, export service, audit |
| **Superset** | Engine truy vấn, dataset/chart/dashboard, RBAC, RLS, MCP (AI agent) |
| **Provisioning Service** | Đồng bộ user/role/RLS/dashboard RBAC từ Portal → Superset |

End-user **không đăng nhập Superset trực tiếp**. Mọi thao tác đi qua Portal (embed hoặc proxy API).

### 1.2. Sơ đồ thành phần

```
                         ┌─────────────────────────────────────┐
                         │  Ingress                            │
                         │  portal.your-co.com  (Phase 1+)     │
                         │  superset.your-co.com (internal)    │
                         └──────────────┬──────────────────────┘
                                        │
              ┌─────────────────────────┼─────────────────────────┐
              ▼                         ▼                         ▼
     ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
     │  Portal App     │      │  Superset Node  │      │  MCP Service    │
     │  (FastAPI/Flask)│─────▶│  (Helm K8s)     │◀─────│  (optional)     │
     └────────┬────────┘      └────────┬────────┘      └─────────────────┘
              │                        │
              ▼                        ▼
     ┌─────────────────┐      ┌─────────────────┐
     │  Portal DB      │      │  Superset DB    │
     │  (PostgreSQL)   │      │  (PostgreSQL)   │
     └─────────────────┘      └─────────────────┘
              │
              ▼
     ┌─────────────────┐
     │  Redis          │
     │  (session/cache)│
     └─────────────────┘
```

### 1.3. Luồng nghiệp vụ tổng quát (tham chiếu)

```
[CNTT CV] ──AI──▶ SQL draft ──▶ [CNTT LD duyệt + share ALL|SELECTED]
                                        │
                                        ▼
                              Mẫu publish → Superset
                                        │
[Ban NV CV] ◀── xem mẫu ────────────────┘
     │
     ▼
 Tạo giao dịch kết xuất ──▶ [Ban NV LD duyệt] ──▶ Tải CSV/XLSX/PDF
```

---

## 2. Ma trận quyết định đã chốt

| # | Hạng mục | Quyết định |
|---|---|---|
| 1 | Kiến trúc | Portal quy trình + Superset engine |
| 2 | Multi-tenant | Nhiều doanh nghiệp, phòng ban **động** |
| 3 | AI | Tùy chọn enable/disable, LLM nội bộ hoặc cloud theo tenant |
| 4 | Kết xuất | CSV + Excel (XLSX) + PDF |
| 5 | Chia sẻ mẫu | `ALL` (tất cả dept) hoặc `SELECTED` (chọn từng dept) |
| 6 | SSO/LDAP | Tùy chọn enable/disable theo tenant |
| 7 | Ký số | Tùy chọn; **bật = 100% user login bằng chứng thư số** |
| 8 | **Giao diện** | Enterprise, responsive, white-label tenant, accessibility AA (§14) |

### 2.1. Nguyên tắc kỹ thuật (ràng buộc xuyên suốt)

| # | Nguyên tắc | Ý nghĩa |
|---|---|---|
| P1 | **Portal owns IAM & workflow** | Superset không expose login cho end-user |
| P2 | **Feature flag theo tenant** | SSO, PKI, AI — bật/tắt độc lập |
| P3 | **Least privilege** | Export chỉ sau duyệt LD Ban, qua Portal API |
| P4 | **Audit mọi hành động nhạy cảm** | Login, duyệt, download — immutable log |
| P5 | **UI nhất quán trước feature** | Shell + design system (§14) từ Phase 0, không “vá UI” cuối |
| P6 | **Không secret trong git** | Vault / K8s Secret / Sealed Secrets |

---

## 3. Sơ đồ Phase nối tiếp

```
Phase 0: Chuẩn bị & scaffold
    │
    ▼
Phase 1: Login Local + Tenant + Session          ← BẮT ĐẦU TỪ ĐÂY (login)
    │
    ▼
Phase 2: SSO/LDAP (feature flag, tùy chọn)
    │
    ▼
Phase 3: Ký số PKI login (feature flag, tùy chọn)
    │
    ▼
Phase 4: Phòng ban động + gán vai trò user
    │
    ▼
Phase 5: Provisioning Superset (role blueprint)
    │
    ▼
Phase 6: RLS multi-tenant / dept
    │
    ▼
Phase 7: AI Orchestrator + MCP (feature flag)
    │
    ▼
Phase 8: Workflow CNTT — tạo & duyệt mẫu
    │
    ▼
Phase 9: Chia sẻ mẫu ALL / SELECTED
    │
    ▼
Phase 10: Giao dịch kết xuất — Ban NV CV
    │
    ▼
Phase 11: Duyệt LD Ban + Export CSV/XLSX/PDF
    │
    ▼
Phase 12: Audit, hardening & production GA
```

**Quy tắc:** Phase N+1 **phụ thuộc** Phase N. Không nhảy phase.

### 3.1. Bảng tóm tắt Phase (tra cứu nhanh)

| Phase | Tên | Backend chính | UI chính (§14) | Gate trọng tâm |
|:---:|---|---|---|---|
| 0 | Scaffold | Health, migration | Design tokens, app shell skeleton | Stack chạy < 15 phút |
| 1 | Login local | Session, `/auth/*` | Login page, dashboard shell | Multi-tenant session |
| 2 | SSO/LDAP | Auth adapters | SSO button, settings form | §12 LDAP/OIDC |
| 3 | PKI login | Challenge/verify | Cert wizard step | 100% user cert khi bật |
| 4 | Dept động | CRUD dept, roles | Admin dept/user tables | Dept isolation |
| 5 | Provision SS | Role sync | — (status toast) | Role auto trên Superset |
| 6 | RLS | Macro Jinja sync | — | Query isolation |
| 7 | AI | MCP orchestrator | AI prompt panel + SQL editor | AI off = manual OK |
| 8 | Workflow CNTT | Template FSM | Template builder, approval queue | Publish dashboard |
| 9 | Share mẫu | ALL / SELECTED | Share scope picker | Dept mới + ALL |
| 10 | Giao dịch CV | Transaction CRUD | Tx form + preview table | CV không download |
| 11 | Duyệt + Export | Export service | Approval drawer + download | 3 formats + audit |
| 12 | GA | Hardening | Polish, a11y audit | Production sign-off |

### 3.2. Luồng phụ thuộc UI

```
Phase 0  App shell + tokens
    └──▶ Phase 1  Login + layout
              └──▶ Phase 2–3  Auth flows (SSO, PKI steps)
                        └──▶ Phase 4  Admin screens
                                  └──▶ Phase 7–11  Workflow screens (dùng chung components)
```

---

## 4. Cấu trúc repo & hạ tầng

### 4.1. Gợi ý cấu trúc thư mục Portal (tạo ở Phase 0)

```
portal/
├── backend/                 # FastAPI hoặc Flask
│   ├── app/
│   │   ├── auth/            # Phase 1–3
│   │   ├── tenants/
│   │   ├── departments/
│   │   ├── provisioning/    # Phase 5–6
│   │   ├── templates/       # Phase 8–9
│   │   ├── transactions/    # Phase 10–11
│   │   ├── export/          # Phase 11
│   │   ├── ai/              # Phase 7
│   │   └── audit/
│   ├── migrations/
│   └── tests/
├── frontend/                # React 18 + TypeScript + Vite (§14)
│   ├── src/
│   │   ├── app/             # Router, providers, layout shell
│   │   ├── features/        # auth, templates, transactions, admin, ...
│   │   ├── components/      # UI primitives (Button, DataTable, StatusBadge, ...)
│   │   ├── design-system/   # tokens, theme, typography
│   │   ├── hooks/
│   │   ├── i18n/            # vi, en
│   │   └── api/             # typed API client
│   └── package.json
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.portal.yml
│   ├── docker-compose.auth-test.yml   # §12 — LDAP, Keycloak, Step CA
│   └── auth-test/
│       ├── ldap/bootstrap.ldif
│       ├── keycloak/realm-demo-corp.json
│       ├── pki/
│       └── scripts/issue-test-cert.sh
└── k8s/
    └── helm/portal/
```

Superset giữ nguyên trong repo hiện tại (`superset/`, `helm/my-values.prod.yaml`).

### 4.2. Hạ tầng tối thiểu

| Thành phần | Phase cần | Ghi chú |
|---|---|---|
| PostgreSQL (Portal DB) | 0 | DB riêng, không dùng chung Superset metadata |
| Redis | 1 | Session, cache |
| Superset K8s | 5 | Đã có theo `helm/README-K8S-PRODUCTION.md` |
| Ingress riêng Portal | 1 | `portal.your-co.com` |
| Auth test stack (dev) | 2–3 | §12 — `portal/docker/docker-compose.auth-test.yml` |
| Vault / K8s Secrets | 2+ | SSO secret, AI key, CA trust store |

---

## 5. ERD & Schema dữ liệu Portal

### 5.1. Sơ đồ quan hệ (rút gọn)

```
tenants ──1:1── tenant_settings
   │
   ├──1:N── departments
   ├──1:N── users
   │           ├── user_auth_identities
   │           ├── user_certificates (Phase 3)
   │           └── user_dept_roles ──N:1── departments
   │
   ├── export_templates (Phase 8)
   │       ├── template_shares (Phase 9, khi SELECTED)
   │       └── template_share_all (Phase 9, khi ALL)
   │
   └── export_transactions (Phase 10)
           ├── transaction_approvals
           ├── transaction_exports
           └── download_tokens
```

### 5.2. Bảng `tenants`

| Cột | Kiểu | Mô tả |
|---|---|---|
| `id` | UUID PK | |
| `slug` | VARCHAR UNIQUE | Mã tenant, vd: `congty-a` |
| `name` | VARCHAR | Tên doanh nghiệp |
| `status` | ENUM | `active`, `suspended`, `archived` |
| `created_at` | TIMESTAMPTZ | |

### 5.3. Bảng `tenant_settings`

| Cột | Kiểu | Phase | Mô tả |
|---|---|---|---|
| `tenant_id` | UUID FK | 1 | |
| `sso_ldap_enabled` | BOOLEAN DEFAULT false | 2 | |
| `auth_mode` | ENUM | 2 | `local`, `oidc`, `saml`, `ldap` |
| `sso_config` | JSONB | 2 | Cấu hình IdP (secret ref) |
| `digital_signature_enabled` | BOOLEAN DEFAULT false | 3 | |
| `pki_config` | JSONB | 3 | CA provider, OCSP URL, ... |
| `ai_enabled` | BOOLEAN DEFAULT false | 7 | |
| `ai_config` | JSONB | 7 | Provider, model, endpoint |
| `export_formats` | TEXT[] | 11 | `['csv','xlsx','pdf']` |
| `download_token_ttl_hours` | INT DEFAULT 24 | 11 | |
| `branding` | JSONB | 1 | §14.3 — logo_url, primary_color, app_name |

### 5.4. Bảng `users`

| Cột | Kiểu | Phase | Mô tả |
|---|---|---|---|
| `id` | UUID PK | 1 | |
| `tenant_id` | UUID FK | 1 | |
| `username` | VARCHAR | 1 | Unique trong tenant |
| `email` | VARCHAR | 1 | |
| `password_hash` | VARCHAR NULL | 1 | NULL khi chỉ SSO |
| `display_name` | VARCHAR | 1 | |
| `system_role` | ENUM | 1 | `tenant_admin`, `cntt_chuyenvien`, `cntt_lanhdao`, `dept_user` |
| `status` | ENUM | 1 | `active`, `inactive`, `locked` |
| `last_login_at` | TIMESTAMPTZ | 1 | |

### 5.5. Bảng `user_auth_identities`

| Cột | Kiểu | Phase | Mô tả |
|---|---|---|---|
| `id` | UUID PK | 2 | |
| `user_id` | UUID FK | 2 | |
| `provider` | ENUM | 2 | `local`, `oidc`, `saml`, `ldap` |
| `external_id` | VARCHAR | 2 | `sub` / `uid` từ IdP |
| `raw_attributes` | JSONB | 2 | Snapshot attributes lần login cuối |

### 5.6. Bảng `user_certificates` (Phase 3)

| Cột | Kiểu | Mô tả |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID FK | |
| `serial_number` | VARCHAR | Serial cert |
| `subject_dn` | VARCHAR | Distinguished Name |
| `issuer_dn` | VARCHAR | |
| `not_before` | TIMESTAMPTZ | |
| `not_after` | TIMESTAMPTZ | |
| `is_active` | BOOLEAN | |
| `registered_at` | TIMESTAMPTZ | |

### 5.7. Bảng `departments` (Phase 4)

| Cột | Kiểu | Mô tả |
|---|---|---|
| `id` | UUID PK | |
| `tenant_id` | UUID FK | |
| `code` | VARCHAR | Unique trong tenant, vd: `KETOAN` |
| `name` | VARCHAR | Tên phòng ban |
| `status` | ENUM | `active`, `inactive` |

### 5.8. Bảng `user_dept_roles` (Phase 4)

| Cột | Kiểu | Mô tả |
|---|---|---|
| `user_id` | UUID FK | |
| `department_id` | UUID FK | |
| `role` | ENUM | `chuyenvien`, `lanhdao` |

> Một user CNTT có thể **không** có bản ghi ở đây (dùng `system_role`). User ban NV có thể thuộc 1+ dept.

### 5.9. Bảng `export_templates` (Phase 8)

| Cột | Kiểu | Mô tả |
|---|---|---|
| `id` | UUID PK | |
| `tenant_id` | UUID FK | |
| `name` | VARCHAR | Tên mẫu |
| `description` | TEXT | |
| `sql_snapshot` | TEXT | SQL tại thời điểm duyệt |
| `superset_dashboard_id` | INT NULL | ID dashboard Superset sau publish |
| `superset_dataset_id` | INT NULL | |
| `status` | ENUM | `draft`, `review`, `published`, `archived` |
| `share_mode` | ENUM NULL | `ALL`, `SELECTED` (set khi publish) |
| `share_scope_version` | INT DEFAULT 0 | |
| `created_by` | UUID FK | CV CNTT |
| `published_by` | UUID FK NULL | LD CNTT |
| `published_at` | TIMESTAMPTZ NULL | |

### 5.10. Bảng `template_shares` (Phase 9, mode SELECTED)

| Cột | Kiểu | Mô tả |
|---|---|---|
| `template_id` | UUID FK | |
| `department_id` | UUID FK | |
| `shared_at` | TIMESTAMPTZ | |
| `shared_by` | UUID FK | |
| `revoked_at` | TIMESTAMPTZ NULL | |

### 5.11. Bảng `template_share_all` (Phase 9, mode ALL)

| Cột | Kiểu | Mô tả |
|---|---|---|
| `template_id` | UUID FK UNIQUE | |
| `include_future_depts` | BOOLEAN DEFAULT true | Dept mới tự nhận mẫu |
| `effective_from` | TIMESTAMPTZ | |

### 5.12. Bảng `export_transactions` (Phase 10)

| Cột | Kiểu | Mô tả |
|---|---|---|
| `id` | UUID PK | |
| `tenant_id` | UUID FK | |
| `template_id` | UUID FK | |
| `department_id` | UUID FK | |
| `params_json` | JSONB | Tham số: kỳ, đơn vị, ... |
| `status` | ENUM | `draft`, `submitted`, `approved`, `rejected`, `downloaded` |
| `created_by` | UUID FK | CV Ban |
| `submitted_at` | TIMESTAMPTZ NULL | |
| `approved_by` | UUID FK NULL | LD Ban |
| `approved_at` | TIMESTAMPTZ NULL | |

### 5.13. Bảng `transaction_approvals` (Phase 11)

| Cột | Kiểu | Mô tả |
|---|---|---|
| `id` | UUID PK | |
| `transaction_id` | UUID FK | |
| `approver_id` | UUID FK | |
| `action` | ENUM | `approve`, `reject` |
| `comment` | TEXT NULL | |
| `signature_payload_hash` | VARCHAR NULL | Phase 3 bật |
| `signature_value` | TEXT NULL | PKCS#7 / CAdES |
| `signer_cert_serial` | VARCHAR NULL | |
| `signed_at` | TIMESTAMPTZ NULL | |

### 5.14. Bảng `download_tokens` (Phase 11)

| Cột | Kiểu | Mô tả |
|---|---|---|
| `id` | UUID PK | |
| `transaction_id` | UUID FK | |
| `format` | ENUM | `csv`, `xlsx`, `pdf` |
| `token` | VARCHAR UNIQUE | |
| `expires_at` | TIMESTAMPTZ | |
| `used_at` | TIMESTAMPTZ NULL | |
| `file_hash` | VARCHAR NULL | SHA-256 |

### 5.15. Bảng `audit_logs` (mọi Phase)

| Cột | Kiểu | Mô tả |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `tenant_id` | UUID | |
| `actor_id` | UUID NULL | |
| `action` | VARCHAR | vd: `AUTH_LOGIN`, `TEMPLATE_PUBLISH` |
| `entity_type` | VARCHAR | |
| `entity_id` | VARCHAR | |
| `payload` | JSONB | |
| `ip_address` | INET | |
| `created_at` | TIMESTAMPTZ | |

---

## 6. Role Blueprint Superset

### 6.1. Quy ước đặt tên role

```
t_{tenant_slug}_cntt_cv          # CNTT chuyên viên
t_{tenant_slug}_cntt_ld          # CNTT lãnh đạo
t_{tenant_slug}_d_{dept_code}_cv   # Ban NV chuyên viên
t_{tenant_slug}_d_{dept_code}_ld   # Ban NV lãnh đạo
```

### 6.2. Blueprint quyền

| Blueprint | Quyền Superset chính | Export |
|---|---|---|
| `BLUEPRINT_CNTT_CV` | SQL Lab, MCP read/write draft, tạo dataset/chart | **Không** |
| `BLUEPRINT_CNTT_LD` | Xem + publish dashboard, share | **Không** |
| `BLUEPRINT_DEPT_CV` | Xem dashboard (DASHBOARD_RBAC), preview data | **Không** |
| `BLUEPRINT_DEPT_LD` | Xem dashboard, preview | **Không** (download qua Portal API) |

> LD Ban **không** được gán `can_export_data` trên Superset UI — export chỉ qua Portal Export Service sau duyệt.

---

## 7. Chi tiết từng Phase

> **Mẫu Gate:** Backend pass + UI pass (§14.8) + Security pass + Regression phase trước.

---

### Phase 0: Chuẩn bị & Scaffold

**Mục tiêu:** Khung Portal + design system tối thiểu — chưa login.

| Lớp | Phạm vi |
|---|---|
| **Backend** | Docker Compose, Alembic, `GET /health`, bảng `tenants`, `tenant_settings` |
| **Frontend** | Vite + TS, theme tokens (§14.2), **App Shell** (sidebar/header placeholder), route `/health-ui` |
| **Schema** | `tenants`, `tenant_settings` |

**Không làm:** Login, SSO, Superset, workflow screens.

**Deliverables:**
- [ ] `portal/docker-compose.portal.yml` chạy được
- [ ] `GET /health` → 200
- [ ] Migration baseline OK
- [ ] **UI:** `design-system/tokens.ts`, layout `AppShell`, font Inter/system-ui, light theme mặc định
- [ ] **UI:** ESLint + Prettier + strict TypeScript (`no any`)

**Gate 0:**
- [ ] Onboard dev < 15 phút (README env vars)
- [ ] **UI:** App shell render, sidebar collapse, responsive ≥1280px / ≥768px
- [ ] Lighthouse Accessibility ≥ 90 trên trang placeholder

**Phụ thuộc:** —

---

### Phase 1: Login Local + Tenant + Session

**Mục tiêu:** Đăng nhập local, session an toàn, dashboard shell theo vai trò.

| Lớp | Phạm vi |
|---|---|
| **Backend** | CRUD tenant/user, `POST /auth/login|logout`, `GET /auth/me`, Redis session, audit auth |
| **Frontend** | **Login page** (§14.4), protected routes, dashboard home, user menu, tenant badge |
| **Schema** | `users` |

**Seed demo:** `demo-corp` — `admin@demo-corp`, `cntt.cv@demo-corp`, `cntt.ld@demo-corp` / `Pass123!`

**Deliverables:**
- [ ] Auth API + brute-force lock (5 lần)
- [ ] **UI Login:** split layout (brand panel + form), show/hide password, loading state, lỗi rõ ràng
- [ ] **UI Dashboard:** welcome card, quick stats placeholder, sidebar menu theo `system_role`
- [ ] Session timeout configurable (default 8h)

**Gate 1:**
- [ ] Login/logout/me OK; tenant isolation
- [ ] **UI:** Form validation inline; không flash unstyled content (FOUC)
- [ ] **UI:** Keyboard Tab order hợp lý; focus visible trên input/button
- [ ] Session hết hạn → redirect login + toast

**Phụ thuộc:** Gate 0

---

### Phase 2: SSO/LDAP (Feature Flag — Tùy chọn)

**Mục tiêu:** Login qua IdP/LDAP khi tenant bật flag; UI thích ứng theo config.

| Lớp | Phạm vi |
|---|---|
| **Backend** | OIDC/SAML/LDAP adapters, `/auth/sso/*`, `tenant_settings.sso_*` |
| **Frontend** | Nút **「Đăng nhập SSO」** (chỉ khi enabled), trang **Cài đặt xác thực** (tenant_admin) |
| **Test** | Stack §12 |

**Luồng SSO bật:** `/auth/sso/login` → IdP → callback → session (giống Phase 1).

**Deliverables:**
- [ ] ≥1 adapter (OIDC Keycloak khuyến nghị) + LDAP bind
- [ ] Admin settings: toggle + form cấu hình (masked secrets)
- [ ] **UI:** SSO OFF → ẩn nút; SSO ON → primary CTA rõ ràng
- [ ] Audit `AUTH_SSO_*`

**Gate 2:** §12 scenarios T2/T3 + regression Phase 1 (T1).

**Phụ thuộc:** Gate 1

---

### Phase 3: Ký số PKI Login (Feature Flag — Tùy chọn)

**Mục tiêu:** Khi bật flag — **100% user** xác thực cert sau bước login (local/SSO).

| Lớp | Phạm vi |
|---|---|
| **Backend** | `/auth/pki/challenge|verify`, `user_certificates`, OCSP mock |
| **Frontend** | **Wizard bước 2** — chọn cert, trạng thái token, hướng dẫn cài driver (§14.5) |
| **Test** | Step CA §12.5 |

**Chính sách:** Cert hết hạn / thu hồi → từ chối; không role miễn.

**Deliverables:**
- [ ] PKI gate sau auth bước 1
- [ ] **UI:** Progress `Đăng nhập → Xác thực chứng thư số → Hoàn tất`
- [ ] **UI:** Error states: không token, cert hết hạn, OCSP fail
- [ ] Admin toggle PKI + cảnh báo “toàn bộ user cần cert”

**Gate 3:** §12 T4/T5/T6 + SSO+PKI combo.

**Phụ thuộc:** Gate 2 (hoặc Gate 1 nếu tạm bỏ SSO — không khuyến nghị prod)

---

### Phase 4: Phòng ban động + Gán vai trò User

**Mục tiêu:** CRUD phòng ban + gán user; UI admin chuyên nghiệp.

| Lớp | Phạm vi |
|---|---|
| **Backend** | CRUD `departments`, `user_dept_roles`, event `DepartmentCreated` |
| **Frontend** | **Admin → Phòng ban** (DataTable + drawer form), **Admin → Người dùng** (gán dept/role) |
| **Schema** | `departments`, `user_dept_roles` |

**Deliverables:**
- [ ] API dept + user assignment
- [ ] **UI:** Table sort/filter/search, badge trạng thái `active/inactive`
- [ ] **UI:** Confirm modal khi deactivate dept
- [ ] Policy: 1 user / 1 dept (document rõ nếu khác)

**Gate 4:** CRUD OK; `/auth/me` phản ánh dept; UI empty state khi chưa có dept.

**Phụ thuộc:** Gate 3

---

### Phase 5: Provisioning Superset — Role Blueprint

**Mục tiêu:** Portal tự động tạo/sync role Superset và user Superset khi có tenant/dept/user mới.

**Phạm vi:**
- `ProvisioningService` gọi Superset REST API (service account admin)
- Khi `DepartmentCreated` → tạo roles `t_{slug}_d_{code}_cv`, `t_{slug}_d_{code}_ld` từ blueprint
- Khi tenant onboard → tạo `t_{slug}_cntt_cv`, `t_{slug}_cntt_ld`
- Sync user Portal → Superset user + gán roles tương ứng
- Bảng `provisioning_sync_log` (entity, superset_id, status, error)
- Cấu hình Superset: feature flags cơ bản (xem §9)

**Superset cấu hình (Phase 5):**
```python
FEATURE_FLAGS = {
    "DASHBOARD_RBAC": True,
    "GRANULAR_EXPORT_PERMISSIONS": True,
}
```

**Không làm ở Phase này:**
- RLS rule
- Dashboard/template

**Deliverables:**
- [ ] Service account Superset + API key trong Vault
- [ ] Provision tenant roles
- [ ] Provision dept roles on create
- [ ] Sync user on create/update
- [ ] Retry + dead letter khi Superset unavailable

**Tiêu chí kiểm duyệt (Gate 5):**
- [ ] Tạo dept `KETOAN` → 2 role mới xuất hiện trong Superset Security
- [ ] User cntt_cv login Portal → user tương ứng tồn tại Superset với role đúng
- [ ] Xóa dept → role revoked (không xóa nếu còn dashboard gắn — soft deactivate)

**Phụ thuộc:** Phase 4 OK + Superset K8s chạy (`helm/README-K8S-PRODUCTION.md`)

---

### Phase 6: RLS Multi-tenant / Department

**Mục tiêu:** Mỗi dept chỉ truy cập dữ liệu thuộc tenant + dept mình trên Superset.

**Phạm vi:**
- Custom Jinja macro (Superset config): `current_user_tenant()`, `current_user_dept()`
- Portal sync user attributes → Superset `user.extra_json` hoặc custom SecurityManager
- Provisioning: tạo RLS rule per dept role
- `FEATURE_FLAGS["RLS_IN_SQLLAB"] = True`
- Dataset vật lý/virtual có cột `tenant_id`, `dept_code`

**RLS mẫu:**
```sql
tenant_id = '{{ current_user_tenant() }}'
AND dept_code = '{{ current_user_dept() }}'
```

**Không làm ở Phase này:**
- Template workflow
- AI

**Deliverables:**
- [ ] Macro Jinja hoạt động
- [ ] RLS auto-provision khi tạo dept
- [ ] Test query: user dept A không thấy data dept B

**Tiêu chí kiểm duyệt (Gate 6):**
- [ ] User dept A query dataset → chỉ rows dept A
- [ ] CNTT LD (không gắn dept) → policy rõ: thấy all tenant hoặc không — **document & implement 1 lựa chọn**
- [ ] SQL Lab (cntt_cv) có RLS khi flag bật

**Phụ thuộc:** Phase 5 OK

---

### Phase 7: AI Orchestrator + MCP (Feature Flag)

**Mục tiêu:** AI sinh SQL draft (tùy chọn) hoặc nhập tay — UI Template Studio bắt đầu.

| Lớp | Phạm vi |
|---|---|
| **Backend** | LLM adapters, `/ai/generate-sql`, MCP JWT |
| **Frontend** | **AI Assistant panel** trong Studio (§14.6): prompt, streaming response, insert SQL |

**Deliverables:**
- [ ] AI ON/OFF per tenant; manual SQL fallback
- [ ] **UI:** Prompt textarea, nút Generate, loading shimmer, diff SQL optional
- [ ] Rate limit + audit `AI_GENERATE_SQL`

**Gate 7:** AI off = manual OK; SQL nguy hiểm bị chặn; chỉ cntt_cv.

**Phụ thuộc:** Gate 6

---

### Phase 8: Workflow CNTT — Tạo & Duyệt Mẫu

**Mục tiêu:** CV CNTT tạo mẫu (AI/manual) → LD CNTT duyệt → publish Superset.

| Lớp | Phạm vi |
|---|---|
| **Backend** | Template FSM, publish dashboard, API §8.3 |
| **Frontend** | **Template Studio** (§14.6): split view SQL + preview, timeline trạng thái, **Approval Inbox** LD CNTT |

**Deliverables:**
- [ ] Template CRUD + submit/approve/reject
- [ ] **UI Studio:** Monaco/SQL editor, AI panel (Phase 7), status `Draft→Review→Published`
- [ ] **UI Inbox:** bảng hàng chờ, drawer chi tiết, nút Duyệt/Từ chối + comment bắt buộc khi reject
- [ ] PKI ON → step-up modal khi approve

**Gate 8:** End-to-end CNTT workflow; UI responsive; reject có comment hiển thị CV.

**Phụ thuộc:** Gate 7

---

### Phase 9: Chia sẻ Mẫu ALL / SELECTED

**Mục tiêu:** LD CNTT chọn phạm vi chia sẻ khi publish / sửa sau publish.

| Lớp | Phạm vi |
|---|---|
| **Backend** | `share_mode`, `template_shares`, ShareResolver, DASHBOARD_RBAC |
| **Frontend** | **Share Scope Modal** (§14.6): radio ALL / multi-select dept, badge `3/12 phòng ban` |

**Deliverables:**
- [ ] Publish + share API
- [ ] **UI:** Modal với search dept, “Chọn tất cả”, preview danh sách được share
- [ ] Sửa phạm vi → confirm + version audit

**Gate 9:** Scenarios ALL/SELECTED/thu hồi (spec trước); UI badge phạm vi trên card mẫu.

**Phụ thuộc:** Gate 8

---

### Phase 10: Giao dịch Kết xuất — Ban NV Chuyên viên

**Mục tiêu:** CV Ban tạo giao dịch, preview, gửi duyệt — **không** download.

| Lớp | Phạm vi |
|---|---|
| **Backend** | `export_transactions`, preview API, `draft→submitted` |
| **Frontend** | **Mẫu của tôi** (card grid), **Wizard giao dịch** 3 bước (§14.7) |

**Wizard UI:** (1) Chọn mẫu → (2) Tham số dynamic form → (3) Preview + Gửi duyệt

**Deliverables:**
- [ ] Transaction + preview API (≤100 rows)
- [ ] **UI:** Card mẫu, `DataTable` preview skeleton, **không** nút Download
- [ ] Notify LD Ban (email optional Phase 12)

**Gate 10:** CV submit OK; preview đúng; cross-dept 403.

**Phụ thuộc:** Gate 9

---

### Phase 11: Duyệt LD Ban + Export CSV / XLSX / PDF

**Mục tiêu:** LD Ban duyệt → tải CSV/XLSX/PDF; UX audit minh bạch.

| Lớp | Phạm vi |
|---|---|
| **Backend** | ExportService, download tokens, PKI sign on approve |
| **Frontend** | **Approval Queue**, **Download Center** (§14.7) |

**Deliverables:**
- [ ] Export 3 formats + watermark
- [ ] **UI:** Queue FIFO, drawer chi tiết, format picker + progress download
- [ ] **UI:** Tab lịch sử giao dịch (timeline audit)
- [ ] PKI ON → modal ký trước approve/download

**Gate 11:** Download chỉ sau approve; 3 formats; audit hiển thị trên UI.

**Phụ thuộc:** Gate 10

---

### Phase 12: Audit, Hardening & Production GA

**Mục tiêu:** Production-ready — security, performance, **UI polish & a11y**.

| Lớp | Phạm vi |
|---|---|
| **Backend** | OCSP thật, pen test, backup, monitoring |
| **Frontend** | a11y audit WCAG AA, i18n hoàn chỉnh, dark mode (optional), perf (LCP < 2.5s) |

**Deliverables:**
- [ ] `docs/portal/RUNBOOK.md`, Helm `portal/k8s/`
- [ ] **UI:** Lighthouse Performance ≥ 85, Accessibility ≥ 95 (trang chính)
- [ ] **UI:** Empty/error states toàn app; keyboard nav full flow
- [ ] Load test export; sign-off nghiệp vụ + kỹ thuật

**Gate 12 — GA:** Full flow 2 tenant staging; §13 LDAP/PKI pilot; UI sign-off.

**Phụ thuộc:** Gate 11

---

## 8. API Reference (tổng hợp)

### 8.1. Auth (Phase 1–3)

| Method | Path | Phase | Mô tả |
|---|---|---|---|
| POST | `/auth/login` | 1 | Local login |
| POST | `/auth/logout` | 1 | |
| GET | `/auth/me` | 1 | User + tenant + roles |
| GET | `/auth/sso/login` | 2 | Redirect IdP |
| GET | `/auth/sso/callback` | 2 | SSO callback |
| POST | `/auth/pki/challenge` | 3 | Nonce ký số |
| POST | `/auth/pki/verify` | 3 | Xác thực cert |

### 8.2. Admin (Phase 2–4)

| Method | Path | Phase | Mô tả |
|---|---|---|---|
| GET/PATCH | `/tenants/{id}/settings` | 2 | SSO, PKI, AI config |
| CRUD | `/departments` | 4 | |
| CRUD | `/users` | 4 | |
| POST | `/users/{id}/dept-roles` | 4 | Gán dept role |

### 8.3. Templates (Phase 7–9)

| Method | Path | Phase | Mô tả |
|---|---|---|---|
| POST | `/ai/generate-sql` | 7 | AI sinh SQL |
| CRUD | `/templates` | 8 | |
| POST | `/templates/{id}/submit` | 8 | |
| POST | `/templates/{id}/approve` | 8 | |
| POST | `/templates/{id}/reject` | 8 | |
| POST | `/templates/{id}/publish` | 9 | Body: share_mode, department_ids |
| PATCH | `/templates/{id}/share-scope` | 9 | |

### 8.4. Transactions (Phase 10–11)

| Method | Path | Phase | Mô tả |
|---|---|---|---|
| GET | `/departments/{id}/templates` | 10 | |
| POST | `/transactions` | 10 | |
| POST | `/transactions/{id}/preview` | 10 | |
| POST | `/transactions/{id}/submit` | 10 | |
| GET | `/transactions/pending` | 11 | LD Ban queue |
| POST | `/transactions/{id}/approve` | 11 | |
| POST | `/transactions/{id}/reject` | 11 | |
| POST | `/transactions/{id}/download` | 11 | format: csv/xlsx/pdf |

---

## 9. Cấu hình Superset theo Phase

Thêm vào `helm/my-values.prod.yaml` → `configOverrides` theo từng phase:

### Phase 5

```python
FEATURE_FLAGS = {
    "DASHBOARD_RBAC": True,
    "GRANULAR_EXPORT_PERMISSIONS": True,
}
```

### Phase 6

```python
FEATURE_FLAGS = {
    "DASHBOARD_RBAC": True,
    "GRANULAR_EXPORT_PERMISSIONS": True,
    "RLS_IN_SQLLAB": True,
    "ENABLE_TEMPLATE_PROCESSING": True,
}
# + custom Jinja macros module
```

### Phase 7

Deploy MCP Service (xem `superset/mcp_service/README.md`):

```python
MCP_AUTH_ENABLED = True
MCP_RBAC_ENABLED = True
```

### Phase 8–11

- **Không** gán `can_export_data` / `can_export_csv` cho end-user roles
- Chỉ Portal service account có quyền query/export qua API

---

## 10. Checklist kiểm duyệt chung

Trước khi chuyển Phase, reviewer xác nhận:

- [ ] **Regression:** Phase trước vẫn hoạt động
- [ ] **Feature flag OFF:** Không ảnh hưởng tenant chưa bật
- [ ] **Multi-tenant:** Không leak cross-tenant
- [ ] **Audit:** Thao tác nhạy cảm có log
- [ ] **UI (§14.8):** States đủ (loading/empty/error/success); responsive; a11y cơ bản
- [ ] **Docs + Tests:** README phase; unit + 1 integration happy path
- [ ] **Security:** Không secret trong git

---

## 11. Phụ lục

### 11.1. Ma trận vai trò × navigation

**App Shell** (§14.4) — menu sidebar theo role, ẩn route không có quyền:

| Menu | Route | Roles |
|---|---|---|
| Tổng quan | `/dashboard` | Tất cả |
| Cài đặt tenant | `/admin/settings` | tenant_admin |
| Phòng ban & User | `/admin/departments`, `/admin/users` | tenant_admin, cntt_ld |
| Mẫu kết xuất (CNTT) | `/cntt/templates` | cntt_cv, cntt_ld |
| Hàng chờ duyệt mẫu | `/cntt/approvals` | cntt_ld |
| Mẫu của phòng ban | `/dept/templates` | dept_cv, dept_ld |
| Giao dịch kết xuất | `/dept/transactions` | dept_cv, dept_ld |
| Chờ duyệt & Tải file | `/dept/approvals` | dept_ld |
| Nhật ký (read-only) | `/audit` | tenant_admin, cntt_ld |

Header cố định: **logo tenant** · tên user · dept badge · nút đăng xuất · (optional) chuyển ngôn ngữ vi/en.

### 11.2. Mã sự kiện audit (tham chiếu)

| Action | Phase |
|---|---|
| `AUTH_LOGIN` | 1 |
| `AUTH_SSO_LOGIN` | 2 |
| `AUTH_PKI_SUCCESS` | 3 |
| `DEPT_CREATED` | 4 |
| `PROVISION_ROLE` | 5 |
| `RLS_CREATED` | 6 |
| `AI_GENERATE_SQL` | 7 |
| `TEMPLATE_SUBMIT` | 8 |
| `TEMPLATE_PUBLISH` | 8–9 |
| `SHARE_SCOPE_CHANGE` | 9 |
| `TX_SUBMIT` | 10 |
| `TX_APPROVE` | 11 |
| `TX_DOWNLOAD` | 11 |

### 11.3. Tham chiếu repo hiện có

| Tài liệu | Đường dẫn |
|---|---|
| Deploy Superset K8s | `helm/README-K8S-PRODUCTION.md` |
| K8s offline bundle | `scripts/k8s-bundle/README.md` |
| Helm values prod | `helm/my-values.prod.yaml` |
| MCP Service | `superset/mcp_service/README.md` |
| Superset Security | `docs/admin_docs/security/security.mdx` |
| Auth test stack (LDAP/PKI) | `portal/docker/docker-compose.auth-test.yml` |
| LDAP bootstrap LDIF | `portal/docker/auth-test/ldap/bootstrap.ldif` |
| Keycloak realm demo | `portal/docker/auth-test/keycloak/realm-demo-corp.json` |

### 11.4. Ghi chú triển khai tuần tự login

```
Phase 1 ──▶ Phase 2 ──▶ Phase 3
(local)     (SSO opt)   (PKI opt)
   │            │            │
   └────────────┴────────────┘
              │
         Session + /auth/me
              │
              ▼
         Phase 4 trở đi
    (user đã xác thực đầy đủ
     theo config tenant)
```

- **Tenant demo SSO OFF, PKI OFF:** Gate 1 là đủ để sang Phase 4 (nếu muốn tăng tốc — vẫn nên hoàn Gate 2–3 trước production).
- **Production:** Bắt buộc Gate 1 + 2 + 3 hoàn hoặc có exception có approval.
- **Production LDAP/PKI:** xem thêm §13 trước khi bật feature flag trên tenant thật.

---

## 12. Docker images test LDAP & Ký số (dev/staging)

Phục vụ **Phase 2 (Gate 2)** và **Phase 3 (Gate 3)** trên máy dev/staging — **không** dùng trực tiếp cho production.

### 12.1. Bảng image & cổng

| Service | Image | Tag khuyến nghị | Port host | Mục đích |
|---|---|---|---|---|
| **OpenLDAP** | `osixia/openldap` | `1.5.0` | `1389` (LDAP), `1636` (LDAPS) | LDAP bind trực tiếp (Phase 2) |
| **phpLDAPadmin** | `osixia/phpldapadmin` | `0.9.0` | `18081` (hoặc `PHPLDAPADMIN_PORT`) | UI quản trị LDAP, kiểm tra user/OU |
| **Keycloak** | `quay.io/keycloak/keycloak` | `24.0` | `8082` | OIDC IdP (Phase 2 — thay LDAP bind) |
| **Step CA** | `smallstep/step-ca` | `latest` | `9443` | CA nội bộ — cấp cert test (Phase 3) |

**File compose:** `portal/docker/docker-compose.auth-test.yml`

```bash
# Từ root repo
docker compose -f portal/docker/docker-compose.auth-test.yml up -d

# Kiểm tra
docker compose -f portal/docker/docker-compose.auth-test.yml ps
```

### 12.2. Sơ đồ test stack

```
┌─────────────────────────────────────────────────────────────────┐
│  Dev machine / Staging namespace (auth-test)                    │
├─────────────────────────────────────────────────────────────────┤
│  Portal (Phase 1+) ──LDAP bind──▶ openldap:389                  │
│       │              ──OIDC──────▶ keycloak:8080                │
│       │              ──PKI verify─▶ step-ca:9443                │
│       ▼                                                         │
│  Browser ◀── phpLDAPadmin :18081 (admin LDAP)                   │
└─────────────────────────────────────────────────────────────────┘
```

### 12.3. OpenLDAP — user demo & cấu hình Portal

**Base DN:** `dc=demo-corp,dc=local`  
**Admin bind:** `cn=admin,dc=demo-corp,dc=local` / password `admin`  
**LDIF seed:** `portal/docker/auth-test/ldap/bootstrap.ldif`

| uid | mail | password | departmentNumber |
|---|---|---|---|
| `cntt.cv` | cntt.cv@demo-corp.local | Pass123! | CNTT |
| `cntt.ld` | cntt.ld@demo-corp.local | Pass123! | CNTT |
| `ban.cv` | ban.cv@demo-corp.local | Pass123! | KETOAN |
| `ban.ld` | ban.ld@demo-corp.local | Pass123! | KETOAN |

**Cấu hình `tenant_settings.sso_config` (LDAP bind) — ví dụ dev:**

```json
{
  "provider": "ldap",
  "ldap_uri": "ldap://host.docker.internal:1389",
  "bind_dn": "cn=admin,dc=demo-corp,dc=local",
  "bind_password_ref": "secret/portal/ldap-bind",
  "user_base_dn": "ou=people,dc=demo-corp,dc=local",
  "user_filter": "(uid={username})",
  "attribute_mapping": {
    "external_id": "uid",
    "email": "mail",
    "display_name": "cn",
    "dept_code": "departmentNumber"
  }
}
```

**Kiểm tra LDAP từ CLI:**

```bash
ldapsearch -x -H ldap://localhost:1389 \
  -D "cn=admin,dc=demo-corp,dc=local" -w admin \
  -b "ou=people,dc=demo-corp,dc=local" "(uid=cntt.cv)"
```

**Gate 2 — LDAP:** Login Portal với `cntt.cv` / `Pass123!` qua LDAP adapter → `/auth/me` có email + dept.

### 12.4. Keycloak — OIDC (tùy chọn thay LDAP bind)

**Admin console:** http://localhost:8082 — `admin` / `admin`  
**Realm import:** `demo-corp` (file `realm-demo-corp.json`)

| Tham số | Giá trị dev |
|---|---|
| Issuer | `http://localhost:8082/realms/demo-corp` |
| Client ID | `portal` |
| Client secret | `portal-dev-secret-change-in-prod` |
| Redirect URI | `http://localhost:8000/auth/sso/callback` |

**Cấu hình Portal (`auth_mode=oidc`):**

```json
{
  "provider": "oidc",
  "issuer_url": "http://localhost:8082/realms/demo-corp",
  "client_id": "portal",
  "client_secret_ref": "secret/portal/keycloak-client",
  "scopes": ["openid", "profile", "email"],
  "attribute_mapping": {
    "external_id": "sub",
    "email": "email",
    "display_name": "name",
    "dept_code": "department"
  }
}
```

> **Ghi chú:** Production dùng HTTPS issuer; dev có thể dùng HTTP nội bộ.

### 12.5. Step CA — ký số test (Phase 3)

Sau khi stack lên, bootstrap container xuất root CA:

```bash
# Chờ step-ca-bootstrap hoàn tất
docker compose -f portal/docker/docker-compose.auth-test.yml logs step-ca-bootstrap

# Root CA (import vào OS/browser trust store)
ls portal/docker/auth-test/pki/root_ca.crt

# Lấy fingerprint
docker exec portal-auth-step-ca step ca fingerprint --ca-url https://localhost:9443
```

**Cấp cert client test** (cần cài [step CLI](https://smallstep.com/docs/step-cli/) trên máy dev):

```bash
chmod +x portal/docker/auth-test/scripts/issue-test-cert.sh
export STEP_CA_FINGERPRINT="<fingerprint-từ-lệnh-trên>"
portal/docker/auth-test/scripts/issue-test-cert.sh cntt.cv
```

**Import cert vào browser (Chrome):** Settings → Privacy → Security → Manage certificates → Import `cntt.cv.crt` + private key.

**Cấu hình `tenant_settings.pki_config` — dev:**

```json
{
  "ca_provider": "step_ca_dev",
  "trust_store_ref": "secret/portal/pki/root_ca.pem",
  "ocsp_enabled": false,
  "require_cert_at_login": true,
  "require_cert_at_approval": true,
  "allowed_eku": ["clientAuth", "emailProtection"]
}
```

**Gate 3 — PKI:**

1. Bật `digital_signature_enabled=true` trên tenant demo  
2. Login LDAP/OIDC → bước PKI hiện ra  
3. Chọn cert `cntt.cv` → verify OK → `/auth/me` có `cert_serial`  
4. Cert không import / hết hạn → 403  

### 12.6. Ma trận test theo Phase

| Kịch bản | SSO/LDAP | PKI | Kết quả mong đợi |
|---|---|---|---|
| T1 | OFF | OFF | Local login (Phase 1) |
| T2 | LDAP ON | OFF | Bind OpenLDAP → session |
| T3 | OIDC ON | OFF | Keycloak redirect → session |
| T4 | LDAP ON | ON | LDAP + cert bắt buộc |
| T5 | OIDC ON | ON | OIDC + cert bắt buộc |
| T6 | LDAP ON | ON, cert revoked | Login fail sau bước PKI |

### 12.7. Dọn stack test

```bash
docker compose -f portal/docker/docker-compose.auth-test.yml down -v
# Giữ pki/root_ca.crt nếu cần; xóa certs cá nhân trong auth-test/pki/certs/
```

---

## 13. Triển khai K8s Production — LDAP & Ký số

Áp dụng khi tenant production bật `sso_ldap_enabled` và/hoặc `digital_signature_enabled`. Tham chiếu thêm:

- Deploy online: `helm/README-K8S-PRODUCTION.md`
- Deploy offline: `scripts/k8s-bundle/README.md`

### 13.1. Kiến trúc production (Portal + Superset + LDAP + PKI)

```
                         ┌──────────────────────────────────────┐
                         │  Ingress TLS (portal.your-co.com)      │
                         └──────────────────┬───────────────────┘
                                            │
              ┌─────────────────────────────┼─────────────────────────────┐
              ▼                             ▼                             ▼
     ┌─────────────────┐          ┌─────────────────┐          ┌─────────────────┐
     │  Portal pods    │          │  Superset pods  │          │  MCP (optional) │
     │  (LDAP client)  │          │  (internal)     │          │                 │
     └────────┬────────┘          └─────────────────┘          └─────────────────┘
              │
    ┌─────────┴─────────┬──────────────────────┐
    ▼                   ▼                      ▼
┌─────────┐      ┌──────────────┐      ┌──────────────────┐
│ LDAP/   │      │ OCSP/CRL     │      │ User workstation │
│ AD      │      │ (CA nội bộ   │      │ USB Token VNCA   │
│ :636    │      │  hoặc VNCA)  │      │ + browser plugin │
└─────────┘      └──────────────┘      └──────────────────┘
     ▲                                           │
     │         Không đặt LDAP/PKI trong          │
     │         cluster — dùng dịch vụ DN         │
     └───────────────────────────────────────────┘
```

**Nguyên tắc:**

- Portal pod **initiate** LDAP bind / OIDC redirect — không expose LDAP ra Internet.
- Ký số **client-side** (browser + token); Portal chỉ verify chữ ký + cert chain.
- Superset **không** tích hợp LDAP trực tiếp cho end-user — IAM tập trung tại Portal.

### 13.2. So sánh môi trường

| Hạng mục | Dev (§12) | Production K8s |
|---|---|---|
| LDAP | `osixia/openldap` container | AD / OpenLDAP doanh nghiệp |
| OIDC | Keycloak dev | Keycloak/ADFS/Azure AD production |
| PKI | Step CA self-signed | VNCA / BCYT / CA nội bộ |
| TLS Ingress | HTTP localhost | HTTPS + cert-manager |
| Secrets | `.env` / compose | K8s Secret / Vault / Sealed Secrets |
| OCSP | Tắt | **Bật bắt buộc** |

### 13.3. Yêu cầu mạng (NetworkPolicy / Firewall)

| Nguồn | Đích | Port | Ghi chú |
|---|---|---|---|
| Portal pod | LDAP/AD | `636` (LDAPS) hoặc `389`+StartTLS | Ưu tiên LDAPS |
| Portal pod | OIDC issuer | `443` | `issuer_url` HTTPS |
| Portal pod | OCSP/CRL URL | `80`/`443` | Theo CA policy |
| User browser | Portal Ingress | `443` | WSS nếu có realtime |
| Portal pod | Superset Service | `8088` | ClusterIP nội bộ |
| User browser | — | — | **Không** cần route tới LDAP; token USB local |

**DNS:** Portal phải resolve được `ldap.company.internal`, `login.company.com`, OCSP host.

### 13.4. Kubernetes — Secret & ConfigMap

Tạo namespace riêng (khuyến nghị):

```bash
kubectl create namespace portal
kubectl create namespace superset   # nếu chưa có
```

**Secrets Portal (không commit git):**

| Secret key | Nội dung | Phase |
|---|---|---|
| `portal-db-url` | PostgreSQL connection string | 0+ |
| `portal-redis-url` | Redis URL | 1+ |
| `portal-session-secret` | Random 64 bytes | 1+ |
| `ldap-bind-password` | Password bind LDAP (nếu dùng) | 2+ |
| `oidc-client-secret` | OIDC client secret | 2+ |
| `pki-root-ca-bundle` | PEM chain CA (VNCA + intermediate) | 3+ |
| `pki-ocsp-url` | URL OCSP (config hoặc env) | 12 |
| `superset-service-token` | API key provision Superset | 5+ |

**Ví dụ Sealed Secret / kubectl (placeholder):**

```bash
kubectl -n portal create secret generic portal-ldap \
  --from-literal=bind_dn='CN=svc-portal,OU=Service,DC=company,DC=local' \
  --from-literal=bind_password='CHANGE_ME'

kubectl -n portal create secret generic portal-pki \
  --from-file=root_ca.pem=./ca-bundle-vnca.pem
```

**ConfigMap `portal-auth-config` (non-sensitive):**

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: portal-auth-config
  namespace: portal
data:
  LDAP_URI: "ldaps://ldap.company.internal:636"
  LDAP_USER_BASE: "OU=Users,DC=company,DC=local"
  LDAP_USER_FILTER: "(sAMAccountName={username})"
  OIDC_ISSUER: "https://login.company.com/realms/production"
  PKI_OCSP_ENABLED: "true"
  PKI_REQUIRE_LOGIN_CERT: "true"
```

### 13.5. Portal Deployment — mount CA trust store

Portal backend cần trust CA để verify cert user và gọi LDAPS:

```yaml
# Fragment — portal Deployment
spec:
  template:
    spec:
      volumes:
        - name: pki-trust
          secret:
            secretName: portal-pki
      containers:
        - name: portal
          volumeMounts:
            - name: pki-trust
              mountPath: /etc/ssl/portal-ca
              readOnly: true
          env:
            - name: SSL_CERT_DIR
              value: /etc/ssl/portal-ca
            - name: LDAP_URI
              valueFrom:
                configMapKeyRef:
                  name: portal-auth-config
                  key: LDAP_URI
            - name: LDAP_BIND_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: portal-ldap
                  key: bind_password
            - name: PKI_ROOT_CA_PATH
              value: /etc/ssl/portal-ca/root_ca.pem
            - name: PKI_OCSP_ENABLED
              value: "true"
```

**Init container (optional)** — kiểm tra LDAP reachable trước khi start:

```yaml
initContainers:
  - name: wait-ldap
    image: busybox:1.36
    command: ['sh', '-c', 'nc -zvw5 ldap.company.internal 636']
```

### 13.6. Ingress — HTTPS & header cho SSO

```yaml
# Fragment — Ingress portal
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: portal
  namespace: portal
  annotations:
    nginx.ingress.kubernetes.io/proxy-buffer-size: "16k"
    nginx.ingress.kubernetes.io/proxy-body-size: "50m"
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  ingressClassName: nginx
  tls:
    - hosts: [portal.your-co.com]
      secretName: portal-tls
  rules:
    - host: portal.your-co.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: portal
                port:
                  number: 8000
```

**OIDC redirect URI production:** `https://portal.your-co.com/auth/sso/callback` — đăng ký trên IdP **trước** khi bật tenant.

**Cookie session:**

```yaml
env:
  - name: SESSION_COOKIE_SECURE
    value: "true"
  - name: SESSION_COOKIE_SAMESITE
    value: "Lax"   # Strict nếu không embed cross-site
```

### 13.7. Cấu hình tenant production (LDAP)

```json
{
  "provider": "ldap",
  "ldap_uri": "ldaps://ldap.company.internal:636",
  "bind_dn": "CN=svc-portal,OU=Service,DC=company,DC=local",
  "bind_password_ref": "k8s:portal/portal-ldap#bind_password",
  "user_base_dn": "OU=Users,DC=company,DC=local",
  "user_filter": "(&(objectClass=user)(sAMAccountName={username}))",
  "start_tls": false,
  "verify_tls": true,
  "attribute_mapping": {
    "external_id": "sAMAccountName",
    "email": "mail",
    "display_name": "displayName",
    "dept_code": "department"
  }
}
```

**Checklist LDAP production:**

- [ ] Service account LDAP chỉ quyền **read** user/group
- [ ] LDAPS cert của AD/LDAP server được trust (mount CA vào Portal)
- [ ] Timeout connect ≤ 10s, pool size cấu hình
- [ ] Fallback local **tắt** khi tenant bật SSO (policy rõ ràng)
- [ ] Audit log không ghi password / bind secret

### 13.8. Cấu hình tenant production (Ký số — VNCA / CA nội bộ)

```json
{
  "ca_provider": "vnca",
  "trust_store_ref": "k8s:portal/portal-pki#root_ca.pem",
  "ocsp_enabled": true,
  "ocsp_url": "http://ocsp.vnca.gov.vn",
  "crl_enabled": true,
  "require_cert_at_login": true,
  "require_cert_at_approval": true,
  "session_reauth_minutes": 15,
  "allowed_eku": ["clientAuth"],
  "reject_expired": true,
  "reject_revoked": true
}
```

**Luồng user production:**

1. Truy cập `https://portal.your-co.com`
2. LDAP/OIDC (nếu bật) — username/password hoặc SSO redirect
3. Browser plugin / native app đọc USB Token → ký challenge Portal
4. Portal verify chain → OCSP/CRL → session

**Yêu cầu workstation (document cho end-user):**

- Cài driver token (VNCA-link, BCYTTools, …)
- Import root CA vào trust store OS
- Browser supported: Chrome/Edge/Cốc Cốc (kiểm tra với plugin nhà cung cấp)

**Không triển khai USB token driver trong container K8s** — ký số luôn **client-side**.

### 13.9. Tích hợp với Superset Helm (cùng cluster)

Superset giữ **internal** — không cấu hình LDAP cho end-user:

```yaml
# helm/my-values.prod.yaml — bổ sung khi có Portal
ingress:
  hosts:
    - superset-internal.your-co.com   # chỉ nội bộ / VPN

configOverrides:
  proxy_fix: |
    ENABLE_PROXY_FIX = True
    PREFERRED_URL_SCHEME = "https"
  feature_flags: |
    FEATURE_FLAGS = {
        "DASHBOARD_RBAC": True,
        "GRANULAR_EXPORT_PERMISSIONS": True,
        "RLS_IN_SQLLAB": True,
        "ENABLE_TEMPLATE_PROCESSING": True,
    }
```

Portal gọi Superset qua **ClusterIP**:

```
SUPERSET_INTERNAL_URL=http://superset.superset.svc.cluster.local:8088
SUPERSET_SERVICE_USERNAME=portal_provisioner
SUPERSET_SERVICE_API_KEY=<from secret>
```

NetworkPolicy: chỉ cho phép `namespace: portal` → `namespace: superset` port 8088.

### 13.10. Offline bundle (`scripts/k8s-bundle`)

Khi cluster **không có internet**, bổ sung image vào bundle:

| Image bổ sung | Khi nào |
|---|---|
| `portal:<TAG>` | Luôn (khi deploy Portal) |
| `postgres:17`, `redis:7` | Portal DB/Redis (nếu không dùng managed) |
| **Không** đóng gói OpenLDAP/Keycloak/Step CA | Production dùng LDAP/CA doanh nghiệp |

**Trên máy deploy:**

```bash
# Sau build-bundle Superset, thêm image Portal
docker build -t docker.io/tuantahp/portal:1.0.0 -f portal/docker/Dockerfile portal/
docker save docker.io/tuantahp/portal:1.0.0 -o dist/images/portal-1.0.0.tar

# Copy CA bundle + ldap secret qua K8s Secret (không nằm trong image)
kubectl apply -f k8s/portal/secrets/   # sealed hoặc inject CI
```

### 13.11. Quy trình bật LDAP/PKI trên tenant production

```
1. Triển khai Portal Phase 1–11 (feature flag OFF) → smoke test local auth
2. Cấu hình Secret LDAP + test bind từ pod:
     kubectl -n portal exec -it deploy/portal -- ldapwhoami -H $LDAP_URI ...
3. Bật sso_ldap_enabled trên 1 tenant pilot → Gate 2 production
4. Cấu hình Secret PKI root CA + OCSP
5. Pilot 5–10 user cài token → bật digital_signature_enabled → Gate 3 production
6. Mở rộng toàn tenant / thêm tenant
```

**Rollback:** Tắt flag trên tenant → user fallback local (nếu policy cho phép) hoặc read-only mode.

### 13.12. Checklist kiểm duyệt production (LDAP + PKI)

**LDAP:**

- [ ] LDAPS hoạt động từ pod Portal
- [ ] User thật login qua LDAP → dept mapping đúng
- [ ] Không leak LDAP bind password trong log
- [ ] IdP/OIDC redirect URI HTTPS khớp production

**PKI:**

- [ ] 100% user pilot login bằng cert — không bypass
- [ ] Cert hết hạn / thu hồi → từ chối
- [ ] OCSP/CRL phản hồi trong SLA (< 3s)
- [ ] Step-up ký khi LD Ban duyệt (Phase 11) hoạt động với token
- [ ] Runbook hỗ trợ user: mất token, hết hạn cert, đổi máy

**K8s:**

- [ ] Secret rotate procedure documented
- [ ] Ingress TLS A+ / no mixed content
- [ ] NetworkPolicy LDAP/OCSP egress chỉ từ Portal namespace
- [ ] Backup Portal DB gồm `user_certificates`, `audit_logs`

### 13.13. Troubleshooting nhanh

| Triệu chứng | Nguyên nhân thường gặp | Hướng xử lý |
|---|---|---|
| LDAP timeout | Firewall chặn 636 | Mở egress pod → LDAP; test `nc` |
| LDAP invalid credentials | Bind DN sai | Kiểm secret `portal-ldap` |
| OIDC redirect mismatch | URI chưa đăng ký IdP | Thêm exact callback HTTPS |
| PKI cert not trusted | Thiếu intermediate CA | Bổ sung full chain vào `portal-pki` |
| OCSP soft fail | CA nội bộ offline | Policy: hard fail vs grace (document) |
| Token không hiện browser | Driver chưa cài | Hướng dẫn user cài VNCA-link |
| SSO OK nhưng không vào PKI | Flag PKI off tenant khác | Kiểm tra `tenant_settings` đúng tenant |

---

## 14. Hệ thống thiết kế giao diện (UI/UX)

> **Bắt buộc từ Phase 0.** Mọi màn hình mới dùng component library nội bộ — không tạo UI ad-hoc từng Phase.

### 14.1. Nguyên tắc thiết kế

| Nguyên tắc | Mô tả |
|---|---|
| **Tin cậy doanh nghiệp** | Giao diện nghiêm túc, rõ ràng — phù hợp cơ quan/doanh nghiệp, tránh màu neon / clutter |
| **Workflow-first** | Luồng duyệt là trung tâm: inbox, trạng thái, hành động tiếp theo luôn visible |
| **Progressive disclosure** | Form phức tạp (AI, share scope) trong drawer/wizard — không nhồi một trang |
| **Fail gracefully** | Mọi API error → toast + inline message; không silent fail |
| **Accessible by default** | WCAG 2.1 AA — contrast, keyboard, screen reader labels |
| **White-label tenant** | Logo + màu primary theo `tenant_settings.branding` |

### 14.2. Tech stack frontend

| Lớp | Lựa chọn | Ghi chú |
|---|---|---|
| Framework | **React 18+** | Functional components + hooks |
| Language | **TypeScript strict** | Không `any`; types từ OpenAPI codegen |
| Build | **Vite** | HMR nhanh cho dev |
| UI library | **Ant Design 5** | Enterprise components; theme token API |
| Styling | **CSS-in-JS (antd token)** + CSS modules cho layout | Tránh custom CSS rải rác |
| Router | **React Router v6** | Protected routes + role guard |
| Data fetching | **TanStack Query** | Cache, retry, loading states |
| Forms | **React Hook Form + Zod** | Validation schema share với backend |
| i18n | **react-i18next** | `vi` (default), `en` |
| Charts preview | **Ant Design Table** / `@ant-design/charts` (optional) | Preview giao dịch |
| SQL editor | **Monaco Editor** | Template studio CNTT |
| Icons | **@ant-design/icons** | Nhất quán stroke |

### 14.3. Design tokens (mặc định — override bởi tenant)

```typescript
// portal/frontend/src/design-system/tokens.ts (concept)
export const defaultTokens = {
  colorPrimary: '#1677ff',      // tenant override: branding.primary_color
  colorSuccess: '#52c41a',      // Approved
  colorWarning: '#faad14',      // Pending review
  colorError: '#ff4d4f',        // Rejected / error
  colorInfo: '#1677ff',
  borderRadius: 8,
  fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  fontSize: 14,
  lineHeight: 1.5715,
  controlHeight: 40,
  motionDurationMid: '0.2s',
};
```

**Typography scale:**

| Token | Size | Dùng cho |
|---|---|---|
| `heading1` | 30px / 600 | Page title |
| `heading2` | 24px / 600 | Section |
| `heading3` | 18px / 600 | Card title |
| `body` | 14px / 400 | Nội dung |
| `caption` | 12px / 400 | Metadata, timestamp |

**Spacing:** bội số **4px** (4, 8, 12, 16, 24, 32, 48).

**Tenant branding (`tenant_settings.branding`):**

```json
{
  "app_name": "Portal Kết xuất",
  "logo_url": "https://cdn.../tenant-logo.svg",
  "primary_color": "#0050b3",
  "favicon_url": "https://cdn.../favicon.ico"
}
```

### 14.4. App Shell (layout chuẩn)

```
┌──────────────────────────────────────────────────────────────────┐
│ Header: [Logo tenant] Portal Kết xuất     🔔  vi|en  [User ▼]   │
├────────────┬─────────────────────────────────────────────────────┤
│ Sidebar    │ Breadcrumb: Trang chủ / Giao dịch / #TX-001          │
│ (collapsible)                                                    │
│ · Tổng quan│ ┌─────────────────────────────────────────────────┐ │
│ · ...      │ │ Page title                    [Primary Action]  │ │
│            │ ├─────────────────────────────────────────────────┤ │
│            │ │ Content area                                    │ │
│            │ └─────────────────────────────────────────────────┘ │
└────────────┴─────────────────────────────────────────────────────┘
```

**Quy tắc layout:**
- Sidebar **240px** (collapsed **64px**); persist preference localStorage
- Content max-width **1440px**, padding **24px**
- Breakpoint **768px:** sidebar → drawer; table → card list
- Login page **không** dùng shell — full viewport branded split (§14.5)

### 14.5. Màn hình xác thực (Phase 1–3)

**Login (Phase 1):**
- Split 50/50: trái brand panel (logo, tagline, illustration tối giản); phải form
- Fields: email/username, password, remember me
- Primary CTA full-width; link quên mật khẩu (Phase 12)
- SSO button (Phase 2) — outline style, icon IdP

**PKI step (Phase 3):**
- Full-page wizard step 2/3; icon shield
- Trạng thái: `Đang chờ token…` · `Chọn chứng thư số` · `Xác thực thành công`
- Link **Hướng dẫn cài đặt token** (modal FAQ)

### 14.6. Màn hình workflow CNTT (Phase 7–9)

**Template Studio (`/cntt/templates/:id`):**
```
┌─────────────────────┬──────────────────────┐
│ AI Assistant panel  │ SQL Editor (Monaco)    │
│ [prompt] [Generate] │                      │
├─────────────────────┴──────────────────────┤
│ Preview table (100 rows max)               │
├────────────────────────────────────────────┤
│ Status: Draft ●  [Lưu nháp] [Gửi duyệt]   │
└────────────────────────────────────────────┘
```

**Approval Inbox LD CNTT:** Table + `StatusBadge` + row action `Xem` → drawer với SQL readonly, preview, nút **Duyệt & Chia sẻ** mở Share Modal.

**Share Scope Modal:**
- Radio: ○ Tất cả phòng ban · ○ Chọn phòng ban
- Multi-select có search; chip hiển thị dept đã chọn
- Summary: “Mẫu sẽ hiển thị cho **12** phòng ban”

### 14.7. Màn hình Ban nghiệp vụ (Phase 10–11)

**Card grid mẫu:** icon format, tên mẫu, mô tả 2 dòng, badge share scope.

**Wizard giao dịch (Steps component):**
1. Chọn mẫu  
2. Form tham số — dynamic fields từ JSON schema  
3. Preview + checkbox “Tôi xác nhận tham số đúng” → **Gửi duyệt**

**Approval Queue LD Ban:**
- Cột: Mã GD · Mẫu · Người gửi · Tham số tóm tắt · Ngày · Trạng thái
- Drawer: timeline audit, preview, **Duyệt** / **Từ chối** (comment required)

**Download Center (sau duyệt):**
- 3 card: CSV · Excel · PDF — icon lớn, mô tả, nút **Tải về**
- Hiển thị: `SHA-256: a1b2…` · Hết hạn token: countdown

### 14.8. Component library bắt buộc

Tạo trong `portal/frontend/src/components/` — **reuse**, không duplicate:

| Component | Props chính | Dùng ở |
|---|---|---|
| `StatusBadge` | `status: draft\|review\|approved\|rejected` | Mọi list |
| `PageHeader` | `title`, `breadcrumb`, `extra` | Mọi trang |
| `DataTable` | sort, filter, pagination, empty | Admin, inbox |
| `ConfirmModal` | destructive actions | Deactivate, reject |
| `EmptyState` | icon, title, description, action | List trống |
| `LoadingSkeleton` | variant table/card/form | Fetching |
| `AuditTimeline` | events[] | Drawer giao dịch |
| `ShareScopePicker` | mode, deptIds, onChange | Phase 9 |
| `FormatDownloadCard` | format, onDownload, loading | Phase 11 |

### 14.9. Trạng thái UI (bắt buộc mọi view có data)

| State | Pattern |
|---|---|
| **Loading** | Skeleton ≥ 300ms; spinner overlay cho submit |
| **Empty** | `EmptyState` + CTA (“Tạo mẫu đầu tiên”) |
| **Error** | Toast + retry button; inline cho form field |
| **Success** | Toast 3s + redirect nếu cần |
| **Forbidden** | Full page 403 friendly + link về dashboard |

### 14.10. Accessibility & i18n

- Contrast text ≥ **4.5:1** (AA)
- Mọi input có `<label>`; icon-only button có `aria-label`
- Focus ring visible; logical tab order
- Key strings trong `i18n/vi.json` + `en.json` — không hard-code tiếng Việt trong JSX (trừ demo seed)

### 14.11. Checklist UI Gate (gắn mọi Phase)

- [ ] Dùng `AppShell` + `PageHeader`
- [ ] Loading / empty / error states
- [ ] Responsive 768px + 1280px
- [ ] Keyboard: submit form bằng Enter; Esc đóng modal
- [ ] Không layout shift khi load (CLS)
- [ ] Role guard — menu ẩn route không authorized

### 14.12. Ánh xạ UI ↔ Phase

| Phase | UI deliverable bắt buộc |
|:---:|---|
| 0 | tokens, AppShell skeleton |
| 1 | Login split, dashboard home |
| 2 | SSO button, admin auth settings |
| 3 | PKI wizard step |
| 4 | Admin dept/user tables |
| 7 | AI panel + SQL editor shell |
| 8 | Template Studio + Approval Inbox |
| 9 | ShareScopePicker modal |
| 10 | Transaction wizard + preview table |
| 11 | Approval Queue + Download Center |
| 12 | a11y audit, i18n complete, perf |

---

**Phiên bản:** 1.2  
**Cập nhật:** 2026-06-05  
**Trạng thái:** Sẵn sàng review — Phase 0 (shell + tokens) → Phase 1 (login). UI: §14. Auth test: §12. K8s: §13.
