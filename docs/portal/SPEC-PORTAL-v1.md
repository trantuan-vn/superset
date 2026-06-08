# Spec Portal Kết xuất Dữ liệu v1.5

> **Mục đích:** Đặc tả triển khai **tuần tự, có Gate kiểm duyệt** cho Portal quy trình kết xuất trên Apache Superset.  
> **Nguyên tắc:** Mỗi Phase = **Backend + Frontend + Gate** → OK mới sang Phase tiếp theo.  
> **Trạng thái:** v1.6 — Phase 0–5 đã triển khai; **workflow thiết kế Superset-first (§1.3)**; UI/UX (§14), auth test (§12), K8s LDAP/PKI (§13), multi-tenant (§2.2), **phân quyền loại tài khoản × phòng ban (§11.1)**.

### Cách đọc tài liệu

| Bạn cần | Đọc |
|---|---|
| Bắt đầu triển khai | §3 bảng tóm tắt → §7 Phase 0 |
| **Onboard doanh nghiệp / PKI theo công ty** | **§2.2** |
| **Phân quyền menu / API / phòng ban** | **§11.1**, §11.4 |
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
2. [Ma trận quyết định đã chốt](#2-ma-trận-quyết-định-đã-chốt) — gồm [§2.2 Tổ chức multi-tenant](#22-mô-hình-tổ-chức-multi-tenant-platform--doanh-nghiệp)
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
[CNTT CV — Template Studio]
     │
     ├─ AI / manual ──▶ SQL draft
     ├─ [Đẩy SQL lên Superset] ──▶ dataset trên Superset
     ├─ [Bắt đầu thiết kế trên Superset] ──▶ tab mới, Launch Bridge auto-login
     │       └── CV thiết kế dashboard X trên Superset
     ├─ [Đồng bộ dashboard] ──▶ Portal hiển thị dashboard X
     └─ [Gửi duyệt] ──▶ Superset: dashboard X published, chỉ CNTT LD xem (DASHBOARD_RBAC)

[CNTT LD — Hàng chờ duyệt]
     ├─ [Mở trên Superset] ──▶ tab mới, auto-login, xem dashboard X
     └─ [Duyệt & chia sẻ] ──▶ chọn phòng ban ALL|SELECTED
              └── Provisioning gán DASHBOARD_RBAC cho role phòng ban trên Superset

[Ban NV CV — Mẫu của phòng ban]
     ├─ [Xem trên Superset] ──▶ tab mới, auto-login, standalone (chỉ xem, không in/kết xuất)
     └─ Tạo giao dịch kết xuất CSV/PDF ──▶ [Ban NV LD duyệt] ──▶ Tải qua Portal API
```

**Launch Bridge:** Portal mint JWT ngắn hạn (`aud=superset-launch`); Superset handler `/login/?portal_launch=…&next=…` thiết lập session cho user đã map provisioning, rồi redirect tới dataset/dashboard. End-user **không** đăng nhập Superset trực tiếp (P1).

**Tách bước thiết kế vs duyệt:** Dashboard do CV thiết kế **thủ công trên Superset** (không auto-publish từ SQL). Portal chỉ đẩy SQL → dataset; publish/RBAC do workflow Portal điều khiển.

---

## 2. Ma trận quyết định đã chốt

| # | Hạng mục | Quyết định |
|---|---|---|
| 1 | Kiến trúc | Portal quy trình + Superset engine |
| 2 | Multi-tenant | Nhiều doanh nghiệp, phòng ban **động**; **platform admin** onboard tenant, **tenant admin** tự quản (§2.2) |
| 3 | AI | Tùy chọn enable/disable, LLM nội bộ hoặc cloud theo tenant |
| 4 | Kết xuất | CSV + Excel (XLSX) + PDF |
| 5 | Chia sẻ mẫu | `ALL` (tất cả dept) hoặc `SELECTED` (chọn từng dept) |
| 6 | SSO/LDAP | Tùy chọn enable/disable theo tenant |
| 7 | Ký số | Tùy chọn; **bật = 100% user login bằng chứng thư số**; CA **upload per-tenant** (§2.2.4) |
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
| P7 | **CA PKI theo tenant** | Mỗi doanh nghiệp upload `root_ca.crt` qua UI — không bắt buộc mount file vào container |

### 2.2. Mô hình tổ chức multi-tenant (Platform ↔ Doanh nghiệp)

Portal phục vụ **nhiều công ty độc lập**. Mỗi công ty là một **tenant**; mỗi tenant có **một hoặc nhiều admin doanh nghiệp** tự quản lý SSO/PKI. Một lớp **platform admin** (vận hành hệ thống) onboard tenant và gán admin — không thay thế admin nội bộ của từng công ty.

#### 2.2.1. Hai lớp quản trị

| Vai trò | `system_role` | Tenant | Trách nhiệm |
|---|---|---|---|
| **Platform admin** | `platform_admin` | `platform` (reserved) | Tạo tenant, gán `tenant_admin`, xem danh sách doanh nghiệp |
| **Tenant admin** | `tenant_admin` | `demo-corp`, `acme`, … | Cài đặt SSO/LDAP, **upload root CA**, bật PKI, quản lý user/dept (Phase 4+) |
| User nghiệp vụ | `cntt_*`, `dept_user` | tenant của mình | Workflow kết xuất — không cấu hình IAM |

**Tenant đặc biệt `platform`:** slug reserved — không dùng cho doanh nghiệp thật. User `platform_admin` đăng nhập với `tenant_slug=platform`.

**Seed dev (tham chiếu):**

| Tenant slug | User | Mật khẩu | `system_role` | Ghi chú |
|---|---|---|---|---|
| `platform` | `admin@platform` | `Pass123!` | `platform_admin` | Quản trị nền tảng |
| `demo-corp` | `admin@demo-corp` | `Pass123!` | `tenant_admin` | Quản trị doanh nghiệp |
| `demo-corp` | `cntt.cv@demo-corp` | `Pass123!` | `cntt_chuyenvien` | Chuyên viên thiết kế mẫu |
| `demo-corp` | `cntt.ld@demo-corp` | `Pass123!` | `cntt_lanhdao` | Lãnh đạo duyệt mẫu (+ IAM) |
| `demo-corp` | `ketoan.cv@demo-corp` | `Pass123!` | `dept_user` | NV phòng KETOAN — `chuyenvien` |
| `demo-corp` | `ketoan.ld@demo-corp` | `Pass123!` | `dept_user` | NV phòng KETOAN — `lanhdao` |

Phòng ban seed: `KETOAN` / *Phòng Kế toán* (tenant `demo-corp`). UI hiển thị **Loại tài khoản** và **Vai trò trong phòng ban** tách biệt (không dùng nhãn nội bộ `CNTT` — xem §11.1).

#### 2.2.2. Sơ đồ phân tầng

```
                    ┌─────────────────────────────────────┐
                    │  Platform admin (tenant: platform)   │
                    │  /platform/tenants                   │
                    │  • Tạo doanh nghiệp + admin đầu tiên │
                    └──────────────────┬──────────────────┘
                                       │ onboard
           ┌───────────────────────────┼───────────────────────────┐
           ▼                           ▼                           ▼
   ┌───────────────┐           ┌───────────────┐           ┌───────────────┐
   │ demo-corp     │           │ acme-corp     │           │ …             │
   │ tenant_admin  │           │ tenant_admin  │           │               │
   │ /admin/settings│          │ /admin/settings│          │               │
   │ • Upload CA   │           │ • Upload CA   │           │               │
   │ • Bật PKI     │           │ • Bật SSO     │           │               │
   └───────┬───────┘           └───────────────┘           └───────────────┘
           │
           ▼
   Loại tài khoản: cntt_chuyenvien, cntt_lanhdao (không gán PB)
                 dept_user → gán PB + chuyenvien|lanhdao (§11.1)
   (PKI verify dùng CA đã upload của demo-corp)
```

#### 2.2.3. Luồng vận hành chuẩn

```
1. Platform admin
   → POST /platform/tenants { slug, name, admin_email, admin_password, … }
   → Tenant + tenant_admin đầu tiên được tạo

2. Tenant admin (đăng nhập slug doanh nghiệp)
   → POST /tenants/{id}/settings/pki/ca-certificate  (upload root_ca.crt)
   → PATCH /tenants/{id}/settings  (digital_signature_enabled=true)
   → Bắt buộc đã upload CA trước khi bật PKI

3. End-user
   → Login local/SSO (bước 1)
   → /login/pki — ký challenge bằng cert do CA của tenant cấp
   → Verify chain theo ca_certificate_pem trong DB (per-tenant)
```

#### 2.2.4. PKI trust store — ưu tiên upload, fallback operator

| Thứ tự | Nguồn | Ai cấu hình | Ghi chú |
|:---:|---|---|---|
| 1 | `pki_config.ca_certificate_pem` | **Tenant admin** (UI upload) | **Khuyến nghị** — mỗi công ty một CA |
| 2 | `pki_config.trust_store_ref` | Operator (secret ref) | Legacy / automation |
| 3 | `PKI_ROOT_CA_PATH` (env) | Operator (mount file) | Chỉ dev shortcut — **không bắt buộc** khi đã upload |

API **không trả** PEM thô — chỉ metadata: `ca_certificate_uploaded`, `ca_subject_dn`, `ca_fingerprint`, `ca_uploaded_at`.

**Ràng buộc:**

- Bật `digital_signature_enabled` **chỉ khi** đã có CA tin cậy (upload hoặc fallback operator).
- Xóa CA → tự tắt PKI nếu không còn nguồn trust khác.
- PKI gate áp dụng **100% user** tenant đó — không role miễn (kể cả `tenant_admin`).

#### 2.2.5. Cấu trúc `pki_config` (sau upload)

```json
{
  "ca_certificate_pem": "<lưu DB — không expose API>",
  "ca_subject_dn": "CN=ACME Internal CA",
  "ca_fingerprint": "<sha256 hex>",
  "ca_uploaded_at": "2026-06-05T10:00:00+00:00",
  "ocsp_enabled": false,
  "require_cert_at_login": true,
  "require_cert_at_approval": true,
  "allowed_eku": ["clientAuth", "emailProtection"],
  "reject_expired": true,
  "reject_revoked": true
}
```

Response API (masked):

```json
{
  "ca_certificate_pem": null,
  "ca_certificate_uploaded": true,
  "ca_subject_dn": "CN=ACME Internal CA",
  "ca_fingerprint": "a1b2c3…",
  "ca_uploaded_at": "2026-06-05T10:00:00+00:00"
}
```

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
| 4 | Dept động | CRUD dept, roles, policy | Admin dept/user tables, 403 guard | Gate 4 + §11.1 |
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
│   │   ├── auth/            # Phase 1–3; policy.py Phase 4
│   │   ├── tenants/
│   │   ├── departments/     # Phase 4 — service, events
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

### 4.3. Reverse proxy Portal Web (Phase 4+)

Container `portal-web` (nginx, port **3000**) proxy các prefix API tới `portal-api:8000`. **Bắt buộc** khai báo mọi prefix backend mới — nếu thiếu, browser nhận `index.html` thay JSON.

| Prefix | Phase | File cấu hình |
|---|---|---|
| `/health` | 0 | `portal/docker/nginx.conf`, `portal/frontend/vite.config.ts` |
| `/auth/` | 1 | ↑ |
| `/tenants/` | 2 | ↑ |
| `/platform/` | 3 | ↑ |
| `/departments` | 4 | ↑ |
| `/users` | 4 | ↑ |

Dev Vite (port **5173**): cùng danh sách proxy trong `portal/frontend/vite.config.ts`.

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
| `slug` | VARCHAR UNIQUE | Mã tenant, vd: `congty-a`. **`platform` reserved** cho vận hành hệ thống |
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
| `pki_config` | JSONB | 3 | Root CA upload (`ca_certificate_pem`), OCSP, EKU — xem §2.2.4 |
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
| `system_role` | ENUM | 1 | `platform_admin`, `tenant_admin`, `cntt_chuyenvien`, `cntt_lanhdao`, `dept_user` |
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

> **Policy Phase 4 (đã triển khai — chi tiết §11.1):**
> - **Loại tài khoản** (`system_role`): `platform_admin`, `tenant_admin`, `cntt_chuyenvien`, `cntt_lanhdao` → **không** có `user_dept_roles`; quyền theo §11.1.1.
> - **Nhân viên phòng ban** (`dept_user`) → **bắt buộc** một bản ghi `user_dept_roles` với `role` ∈ `chuyenvien` | `lanhdao` để có capability phòng ban (§11.1.2).
> - **Một `dept_user` / một phòng ban** — gán PB thứ hai trả **409**; API chỉ chấp nhận gán PB cho `dept_user`.
> - Spec gốc ghi `dept_user` có thể thuộc 1+ dept — **Phase 4 chọn 1 dept/user** để đơn giản RLS Phase 6; nếu đổi policy cần sửa §11.1 và migration.

### 5.9. Bảng `export_templates` (Phase 8)

| Cột | Kiểu | Mô tả |
|---|---|---|
| `id` | UUID PK | |
| `tenant_id` | UUID FK | |
| `name` | VARCHAR | Tên mẫu |
| `description` | TEXT | |
| `sql_snapshot` | TEXT | SQL tại thời điểm duyệt |
| `superset_dashboard_id` | INT NULL | ID dashboard Superset do CV thiết kế |
| `superset_dashboard_title` | VARCHAR NULL | Tiêu đề dashboard tại thời điểm sync |
| `superset_dataset_id` | INT NULL | Dataset virtual tạo từ SQL push |
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
- [ ] **UI Dashboard:** welcome card, quick stats placeholder, sidebar menu theo capability (§11.1)
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

**Mục tiêu:** Khi bật flag — **100% user** xác thực cert sau bước login (local/SSO). Mỗi tenant dùng **CA riêng** do tenant admin upload.

| Lớp | Phạm vi |
|---|---|
| **Backend** | `/auth/pki/challenge|verify`, `user_certificates`, OCSP mock; **upload CA** `POST/DELETE …/pki/ca-certificate`; **platform** `GET/POST /platform/tenants` (§2.2) |
| **Frontend** | **Wizard bước 2** — chọn cert (§14.5); **Admin** upload `root_ca.crt` thay mount file; **Platform** `/platform/tenants` |
| **Test** | Step CA §12.5 |

**Chính sách:** Cert hết hạn / thu hồi → từ chối; không role miễn. Bật PKI chỉ sau khi upload CA (§2.2.3).

**Deliverables:**
- [ ] PKI gate sau auth bước 1
- [ ] **UI:** Progress `Đăng nhập → Xác thực chứng thư số → Hoàn tất`
- [ ] **UI:** Error states: không token, cert hết hạn, OCSP fail
- [ ] Tenant admin: upload/replace/remove root CA + metadata (subject, fingerprint)
- [ ] Tenant admin toggle PKI + cảnh báo “toàn bộ user cần cert”
- [ ] Platform admin: onboard tenant + gán `tenant_admin` đầu tiên

**Gate 3:** §12 T4/T5/T6 + SSO+PKI combo; **2 tenant** với **2 CA khác nhau** không cross-verify.

**Phụ thuộc:** Gate 2 (hoặc Gate 1 nếu tạm bỏ SSO — không khuyến nghị prod)

---

### Phase 4: Phòng ban động + Gán vai trò User

**Mục tiêu:** CRUD phòng ban + gán user; UI admin chuyên nghiệp; phân quyền IAM theo §11.1.

| Lớp | Phạm vi |
|---|---|
| **Backend** | CRUD `departments`, `user_dept_roles`, event `DepartmentCreated`, `app/auth/policy.py` |
| **Frontend** | **Admin → Phòng ban** (DataTable + drawer), **Admin → Người dùng** (CRUD + gán dept/role), `RoleRoute` + trang 403 |
| **Schema** | Migration `0006_departments` — bảng `departments`, `user_dept_roles` |

**Deliverables:**
- [x] API dept + user assignment (`/departments`, `/users`, `/users/{id}/dept-roles`)
- [x] **UI:** Table sort/filter/search, badge trạng thái `active/inactive`
- [x] **UI:** Confirm modal khi deactivate dept / user
- [x] Policy: **1 `dept_user` / 1 phòng ban** (document §5.8)
- [x] `/auth/me` trả `user.departments[]` (code, name, role)
- [x] Ma trận phân quyền backend + frontend (§11.1, §11.4)
- [x] Nginx/Vite proxy `/departments`, `/users` (§4.3)

**File triển khai (tham chiếu):**

| Thành phần | Đường dẫn |
|---|---|
| Models | `portal/backend/app/models/department.py` |
| Service + event | `portal/backend/app/departments/service.py`, `events.py` |
| Policy | `portal/backend/app/auth/policy.py`, `dependencies.py` |
| API | `portal/backend/app/api/departments.py`, `users.py` |
| Migration | `portal/backend/migrations/versions/2026_06_07_0006_departments.py` |
| UI | `portal/frontend/src/pages/AdminDepartmentsPage.tsx`, `AdminUsersPage.tsx` |
| Route guard | `portal/frontend/src/features/auth/permissions.ts`, `RoleRoute.tsx` |
| Tests | `portal/backend/tests/test_departments.py`, `test_policy.py` |

**Gate 4:** CRUD OK; `/auth/me` phản ánh dept; UI empty state khi chưa có dept; URL trái quyền → 403; `cntt_lanhdao` không sửa `tenant_admin`.

**Phụ thuộc:** Gate 3 (demo tenant có thể bỏ qua SSO/PKI — xem §12)

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
- [ ] `cntt_lanhdao` (không có `user_dept_roles` — §11.1.0) → RLS Superset: thấy all tenant hoặc không — **document & implement 1 lựa chọn**
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

### Phase 8: Workflow CNTT — Tạo & Duyệt Mẫu (Superset-first)

**Mục tiêu:** CV CNTT: AI/manual SQL → đẩy dataset Superset → thiết kế dashboard trên Superset → gửi duyệt → LD CNTT review trên Superset → duyệt + chia sẻ phòng ban.

| Lớp | Phạm vi |
|---|---|
| **Backend** | Template FSM, `push-dataset`, `sync-dashboard`, Launch URL, submit → reviewer RBAC, approve → dept RBAC + share |
| **Frontend** | **Template Studio** (§14.6): nút Đẩy SQL / Bắt đầu thiết kế / Đồng bộ dashboard; **Approval Inbox** + Mở Superset + ShareScopePicker |

**Deliverables:**
- [ ] `POST /templates/{id}/push-dataset` — tạo virtual dataset từ SQL
- [ ] `GET /templates/{id}/launch-url?target=…` — Launch Bridge URL (dataset / dashboard_design / dashboard_review / dashboard_view)
- [ ] `POST /templates/{id}/sync-dashboard` — liên kết dashboard CV vừa tạo
- [ ] Submit: bắt buộc dataset + dashboard; Superset DASHBOARD_RBAC chỉ CNTT LD
- [ ] Approve: body `share_mode` + `department_ids`; provisioning mở dashboard cho phòng ban
- [ ] **UI Studio:** card Superset, alert dashboard đã liên kết
- [ ] **UI Inbox:** nút Mở Superset, modal Duyệt & chia sẻ

**Gate 8:** End-to-end: push → design (tab mới) → sync → submit → LD review (tab mới) → approve + share.

**Phụ thuộc:** Gate 7, Superset Launch Bridge handler (§9.5)

---

### Phase 9: Chia sẻ Mẫu ALL / SELECTED

**Mục tiêu:** LD CNTT chọn phạm vi chia sẻ **khi duyệt** (gộp vào approve Phase 8); sửa phạm vi sau publish.

| Lớp | Phạm vi |
|---|---|
| **Backend** | `share_mode`, `template_department_shares`, ShareResolver, DASHBOARD_RBAC dept roles |
| **Frontend** | **ShareScopePicker** trong modal Duyệt (§14.6) |

**Deliverables:**
- [ ] Approve body: `share_mode`, `department_ids`
- [ ] `PATCH /templates/{id}/share-scope` — sửa sau publish
- [ ] **UI:** badge phạm vi trên card mẫu phòng ban

**Gate 9:** ALL/SELECTED/thu hồi; dept user chỉ xem dashboard qua Launch (standalone, không export UI).

**Phụ thuộc:** Gate 8

---

### Phase 10: Giao dịch Kết xuất — Ban NV Chuyên viên

**Mục tiêu:** CV Ban xem dashboard trên Superset (Launch, view-only) → tạo giao dịch preview → gửi duyệt — **không** download trực tiếp từ Superset.

| Lớp | Phạm vi |
|---|---|
| **Backend** | `export_transactions`, preview API, `launch-url?target=dashboard_view` |
| **Frontend** | **Mẫu của tôi** — card + **Xem trên Superset**; **Wizard giao dịch** 3 bước (§14.7) |

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

### 8.2. Platform operator (Phase 3+)

| Method | Path | Role | Mô tả |
|---|---|---|---|
| GET | `/platform/tenants` | `platform_admin` | Danh sách doanh nghiệp (trừ tenant `platform`) |
| POST | `/platform/tenants` | `platform_admin` | Tạo tenant + `tenant_admin` đầu tiên |
| POST | `/platform/tenants/{id}/admins` | `platform_admin` | Thêm `tenant_admin` cho tenant |

Body `POST /platform/tenants` (ví dụ):

```json
{
  "slug": "acme-corp",
  "name": "ACME Corporation",
  "admin_email": "admin@acme-corp",
  "admin_password": "ChangeMe123!",
  "admin_display_name": "ACME Administrator"
}
```

### 8.3. Tenant admin & IAM (Phase 2–4)

#### 8.3.1. Cài đặt tenant — chỉ `tenant_admin`

| Method | Path | Capability | Mô tả |
|---|---|---|---|
| GET/PATCH | `/tenants/{id}/settings` | `tenant.settings` | SSO, PKI flags, AI config |
| POST | `/tenants/{id}/settings/pki/ca-certificate` | `tenant.settings` | Upload `root_ca.crt` (PEM body) |
| DELETE | `/tenants/{id}/settings/pki/ca-certificate` | `tenant.settings` | Xóa CA đã upload |

#### 8.3.2. Phòng ban — `tenant_admin`, `cntt_lanhdao`

| Method | Path | Capability | Mô tả |
|---|---|---|---|
| GET | `/departments` | `iam.admin` | List (query: `search`, `status`) |
| POST | `/departments` | `iam.admin` | Tạo — body: `{ "code", "name" }` |
| GET | `/departments/{id}` | `iam.admin` | Chi tiết |
| PATCH | `/departments/{id}` | `iam.admin` | Sửa tên / `status: inactive` (soft deactivate) |

Body tạo phòng ban:

```json
{
  "code": "KETOAN",
  "name": "Phòng Kế toán"
}
```

#### 8.3.3. Người dùng — `tenant_admin`, `cntt_lanhdao` (hạn chế IAM — §11.1.5)

| Method | Path | Capability | Mô tả |
|---|---|---|---|
| GET | `/users` | `iam.admin` | List (query: `search`, `system_role`) |
| POST | `/users` | `iam.admin` | Tạo user |
| GET | `/users/{id}` | `iam.admin` | Chi tiết |
| PATCH | `/users/{id}` | `iam.admin` | Sửa display_name, email, status |
| POST | `/users/{id}/dept-roles` | `iam.admin` | Gán / cập nhật vai trò phòng ban |
| DELETE | `/users/{id}/dept-roles/{department_id}` | `iam.admin` | Gỡ phân công phòng ban |

Body tạo user:

```json
{
  "username": "ketoan.cv@demo-corp",
  "email": "ketoan.cv@demo-corp",
  "display_name": "Kế toán — Chuyên viên",
  "password": "Pass123!",
  "system_role": "dept_user"
}
```

Body gán phòng ban (**chỉ** khi `system_role = dept_user`; một user / một phòng ban):

```json
{
  "department_id": "a0000000-0000-4000-8000-000000000101",
  "role": "chuyenvien"
}
```

| `system_role` khi tạo user | Gán phòng ban? | `role` hợp lệ |
|---|---|---|
| `tenant_admin` | ❌ | — |
| `cntt_chuyenvien` | ❌ | — |
| `cntt_lanhdao` | ❌ | — |
| `dept_user` | ✅ (bước riêng sau tạo user) | `chuyenvien` \| `lanhdao` |

#### 8.3.4. `/auth/me` — phản ánh loại tài khoản + phòng ban (Phase 4)

```json
{
  "user": {
    "id": "…",
    "username": "ketoan.cv@demo-corp",
    "system_role": "dept_user",
    "departments": [
      {
        "department_id": "…",
        "department_code": "KETOAN",
        "department_name": "Phòng Kế toán",
        "role": "chuyenvien"
      }
    ]
  },
  "tenant": { "…": "…" }
}
```

Body upload CA (Phase 2–3):

```json
{
  "certificate": "-----BEGIN CERTIFICATE-----\n…\n-----END CERTIFICATE-----"
}
```

### 8.4. Templates (Phase 7–9)

| Method | Path | Phase | Mô tả |
|---|---|---|---|
| POST | `/ai/generate-sql` | 7 | AI sinh SQL |
| CRUD | `/templates` | 8 | |
| POST | `/templates/{id}/push-dataset` | 8 | Tạo virtual dataset từ SQL |
| GET | `/templates/{id}/launch-url` | 8 | Query `target`: dataset, dashboard_design, dashboard_review, dashboard_view |
| POST | `/templates/{id}/sync-dashboard` | 8 | Liên kết dashboard CV thiết kế trên Superset |
| POST | `/templates/{id}/submit` | 8 | RBAC reviewer-only trên Superset |
| POST | `/templates/{id}/approve` | 8–9 | Body: `share_mode`, `department_ids` |
| POST | `/templates/{id}/reject` | 8 | |
| PATCH | `/templates/{id}/share-scope` | 9 | Sửa phạm vi sau publish |

### 8.5. Transactions (Phase 10–11)

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
- **Launch Bridge** (§1.3): JWT `aud=superset-launch`, TTL ≤ 120s, map `sub` → Superset username `t_{tenant}__{portal_user}`

### 9.5. Superset Launch Bridge (Phase 8+)

Handler trên Superset (custom view hoặc middleware login):

1. Nhận `portal_launch` JWT + `next` path
2. Verify HS256 với secret dùng chung Portal (`MCP_JWT_SECRET` / `SUPERSET_LAUNCH_JWT_SECRET`)
3. `sub` → user Superset; tạo session Flask-Login
4. Redirect `next` (dataset explore hoặc dashboard standalone/edit)

Deep link:

| `target` | Path Superset |
|---|---|
| `dataset` | `/explore/?datasource_type=table&datasource_id={id}` |
| `dashboard_design` | `/superset/dashboard/{id}/?edit=true` |
| `dashboard_review` / `dashboard_view` | `/superset/dashboard/{id}/?standalone=1` |

View-only (dept user): `standalone=1` + role **không** có export permissions; kết xuất chỉ qua Portal Phase 11.

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

### 11.1. Ma trận vai trò × navigation & phân quyền

**App Shell** (§14.4) — menu sidebar và route guard theo **capability** (§11.4). Ẩn menu + chặn URL trực tiếp (trang 403).

#### 11.1.0. Hai lớp phân quyền (không trộn)

Portal dùng **hai trường độc lập** — UI và API phải hiển thị / kiểm tra đúng từng lớp:

| Lớp | Trường DB | Áp dụng cho | Mô tả |
|---|---|---|---|
| **Loại tài khoản** | `users.system_role` | Mọi user | Quyền **toàn tenant**: IAM, thiết kế mẫu CNTT, cài đặt SSO/PKI, … |
| **Vai trò phòng ban** | `user_dept_roles.role` | Chỉ `dept_user` | Quyền **theo phòng ban đã gán**: xem mẫu, tạo giao dịch, duyệt tải file |

**Quy tắc cứng (Phase 4–5, đã triển khai):**

- `platform_admin`, `tenant_admin`, `cntt_chuyenvien`, `cntt_lanhdao` → **không** có bản ghi `user_dept_roles`; API `POST /users/{id}/dept-roles` trả **422** nếu target không phải `dept_user`.
- `dept_user` → **bắt buộc** gán đúng **một** phòng ban (`user_dept_roles`) trước khi có menu workflow phòng ban (Phase 8+).
- Nhãn UI **「Loại tài khoản」** map `system_role`; cột **「Phòng ban」** / **「Vai trò trong phòng ban」** chỉ có ý nghĩa với `dept_user` (các loại khác hiển thị «Chưa gán» / ẩn form gán PB).

#### 11.1.1. Loại tài khoản (`system_role`) — nhãn UI

| `system_role` | Nhãn UI (vi) | Nhãn UI (en) | Mô tả ngắn (UI) | Gán phòng ban? | Capability mặc định |
|---|---|---|---|---|---|
| `platform_admin` | Quản trị nền tảng | Platform operator | — | ❌ | `platform.tenants` |
| `tenant_admin` | Quản trị doanh nghiệp | Organization admin | Cấu hình SSO/PKI, quản lý phòng ban và người dùng | ❌ | `tenant.settings`, `iam.admin`, `audit.read` |
| `cntt_chuyenvien` | Chuyên viên thiết kế mẫu | Template designer | Soạn và quản lý mẫu kết xuất dữ liệu | ❌ | `cntt.templates` |
| `cntt_lanhdao` | Lãnh đạo duyệt mẫu | Template approver | Duyệt mẫu trước khi chia sẻ cho các phòng ban | ❌ | `iam.admin`, `cntt.templates`, `cntt.approvals`, `audit.read` |
| `dept_user` | Nhân viên phòng ban | Department staff | Tạo giao dịch kết xuất theo mẫu đã được duyệt | ✅ **bắt buộc** | *(qua `user_dept_roles` — §11.1.2)* |

> **Thuật ngữ:** `cntt_*` là mã nội bộ backend/Superset (`t_{slug}_cntt_cv|ld`). Trên UI Portal **không** hiển thị chữ «CNTT» — dùng nhãn *Chuyên viên thiết kế mẫu* / *Lãnh đạo duyệt mẫu*.

#### 11.1.2. Vai trò trong phòng ban (`user_dept_roles.role`)

**Chỉ áp dụng khi `system_role = dept_user`.** Mỗi user tối đa **một** cặp `(department_id, role)`.

| `role` | Nhãn UI (vi) | Nhãn UI (en) | Workflow (Phase 8+) | Capability bổ sung |
|---|---|---|---|---|
| `chuyenvien` | Chuyên viên | Specialist | Xem mẫu PB, tạo & gửi giao dịch kết xuất | `dept.templates`, `dept.transactions` |
| `lanhdao` | Lãnh đạo | Leader | + Duyệt giao dịch & tải file (qua Portal API) | `dept.templates`, `dept.transactions`, `dept.approvals` |

`dept_user` **chưa gán phòng ban** → không có capability phòng ban; sidebar chỉ **Tổng quan** + **Trạng thái hệ thống** (và các mục không yêu cầu PB).

#### 11.1.3. Ma trận tổng hợp — loại tài khoản × phòng ban

Bảng **kết quả quyền** sau khi `has_capability()` (backend) / `hasCapability()` (frontend):

| `system_role` | `user_dept_roles` | Menu / quyền nổi bật |
|---|---|---|
| `platform_admin` | — | `/platform/tenants` |
| `tenant_admin` | — | `/admin/settings`, `/admin/departments`, `/admin/users`, `/audit` |
| `cntt_chuyenvien` | — *(không gán PB)* | `/cntt/templates` |
| `cntt_lanhdao` | — *(không gán PB)* | `/cntt/templates`, `/cntt/approvals`, `/admin/departments`, `/admin/users`, `/audit` |
| `dept_user` | chưa gán PB | Chỉ `/dashboard`, `/health-ui` |
| `dept_user` | `KETOAN` + `chuyenvien` | + `/dept/templates`, `/dept/transactions` *(Phase 8–10)* |
| `dept_user` | `KETOAN` + `lanhdao` | + `/dept/approvals` *(Phase 11)* |

**Ví dụ seed `demo-corp`:**

| User | `system_role` | Phòng ban | `user_dept_roles.role` | Superset role (Phase 5) |
|---|---|---|---|---|
| `admin@demo-corp` | `tenant_admin` | — | — | *(không sync)* |
| `cntt.cv@demo-corp` | `cntt_chuyenvien` | — | — | `t_demo-corp_cntt_cv` |
| `cntt.ld@demo-corp` | `cntt_lanhdao` | — | — | `t_demo-corp_cntt_ld` |
| `ketoan.cv@demo-corp` | `dept_user` | `KETOAN` | `chuyenvien` | `t_demo-corp_d_KETOAN_cv` |
| `ketoan.ld@demo-corp` | `dept_user` | `KETOAN` | `lanhdao` | `t_demo-corp_d_KETOAN_ld` |

#### 11.1.4. Ma trận menu × capability

| Menu | Route | Capability | Điều kiện (đủ **một** dòng) |
|---|---|---|---|
| Tổng quan | `/dashboard` | — | Mọi user đã đăng nhập |
| Quản lý doanh nghiệp | `/platform/tenants` | `platform.tenants` | `system_role = platform_admin` |
| Cài đặt tenant | `/admin/settings` | `tenant.settings` | `system_role = tenant_admin` |
| Phòng ban | `/admin/departments` | `iam.admin` | `tenant_admin` **hoặc** `cntt_lanhdao` |
| Người dùng | `/admin/users` | `iam.admin` | `tenant_admin` **hoặc** `cntt_lanhdao` |
| Mẫu kết xuất | `/cntt/templates` | `cntt.templates` | `cntt_chuyenvien` **hoặc** `cntt_lanhdao` |
| Duyệt mẫu kết xuất | `/cntt/approvals` | `cntt.approvals` | `cntt_lanhdao` |
| Mẫu của phòng ban | `/dept/templates` | `dept.templates` | `dept_user` + đã gán PB + (`chuyenvien` **hoặc** `lanhdao`) |
| Giao dịch kết xuất | `/dept/transactions` | `dept.transactions` | `dept_user` + đã gán PB + (`chuyenvien` **hoặc** `lanhdao`) |
| Chờ duyệt & Tải file | `/dept/approvals` | `dept.approvals` | `dept_user` + đã gán PB + `lanhdao` |
| Nhật ký | `/audit` | `audit.read` | `tenant_admin` **hoặc** `cntt_lanhdao` |
| Trạng thái hệ thống | `/health-ui` | — | Mọi user đã đăng nhập |

> **Phase 4–5:** Route `/dept/*` chưa có UI — `dept_user` đã gán PB vẫn **không thấy** menu đó cho đến Phase 8+. Capability đã sẵn sàng trên `/auth/me` + policy.

#### 11.1.5. Hạn chế IAM (Phase 4)

| Hành động | `tenant_admin` | `cntt_lanhdao` | Ghi chú |
|---|---|---|---|
| Tạo / sửa / vô hiệu `tenant_admin` | ✅ | ❌ | Chỉ `tenant_admin` gán được `tenant_admin` |
| Tạo / sửa `dept_user`, `cntt_*` | ✅ | ✅ | Cần `iam.admin` |
| Gán / sửa `user_dept_roles` | ✅ | ✅ | **Chỉ** target `dept_user`; tối đa 1 phòng ban / user |
| Gỡ `user_dept_roles` | ✅ | ✅ | Target không được là `tenant_admin` |
| Sửa user `tenant_admin` | ✅ | ❌ | `can_modify_user` |
| Cài đặt SSO/PKI | ✅ | ❌ | `tenant.settings` |

Header cố định: **logo tenant** · tên user · **badge phòng ban** (mã PB, vd. `KETOAN`, nếu `dept_user` đã gán) · đăng xuất · (optional) vi/en.

### 11.2. Mã sự kiện audit (tham chiếu)

| Action | Phase |
|---|---|
| `AUTH_LOGIN` | 1 |
| `AUTH_SSO_LOGIN` | 2 |
| `AUTH_PKI_SUCCESS` | 3 |
| `TENANT_CREATED` | 3 |
| `TENANT_ADMIN_ADDED` | 3 |
| `PKI_CA_UPLOADED` | 3 |
| `PKI_CA_REMOVED` | 3 |
| `DEPT_CREATED` | 4 |
| `DEPT_UPDATED` | 4 |
| `DEPT_DEACTIVATED` | 4 |
| `DEPT_REACTIVATED` | 4–5 |
| `USER_CREATED` | 4 |
| `USER_UPDATED` | 4 |
| `USER_DEPT_ROLE_ASSIGNED` | 4 |
| `USER_DEPT_ROLE_REMOVED` | 4 |
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

### 11.4. Triển khai phân quyền (Phase 4)

**Nguyên tắc:** Một nguồn ma trận — backend enforce API, frontend mirror cho menu + route guard. Không tin tưởng sidebar ẩn menu là đủ bảo mật.

#### 11.4.1. Capability enum

| Capability | Mô tả |
|---|---|
| `platform.tenants` | Onboard doanh nghiệp |
| `tenant.settings` | SSO, PKI, branding |
| `iam.admin` | CRUD phòng ban & user |
| `cntt.templates` | Thiết kế mẫu kết xuất |
| `cntt.approvals` | Duyệt mẫu |
| `dept.templates` | Xem mẫu đã share cho phòng ban |
| `dept.transactions` | Tạo giao dịch kết xuất |
| `dept.approvals` | Duyệt giao dịch + download |
| `audit.read` | Xem nhật ký |

#### 11.4.2. File mã nguồn

| Lớp | File |
|---|---|
| Backend policy | `portal/backend/app/auth/policy.py` |
| FastAPI dependencies | `portal/backend/app/auth/dependencies.py` — `require_iam_admin`, `require_tenant_admin`, … |
| Frontend permissions | `portal/frontend/src/features/auth/permissions.ts` |
| Route guard | `portal/frontend/src/features/auth/RoleRoute.tsx` |
| Navigation filter | `portal/frontend/src/features/auth/navConfig.ts` → `navItemsForUser()` |
| Trang 403 | `portal/frontend/src/pages/ForbiddenPage.tsx` |

#### 11.4.3. Luồng kiểm tra

```
Request API / Navigate URL
        │
        ▼
  get_current_user (+ dept_roles nếu cần)
        │
        ▼
  has_capability(user, capability)
        │
   ┌────┴────┐
   ▼         ▼
 200/OK    403 Forbidden
```

`/auth/me` luôn trả `user.departments[]` để frontend tính capability phòng ban mà không gọi thêm API.

#### 11.4.4. Kiểm thử nhanh (Gate 4)

| User | `system_role` | PB / `dept_role` | Hành động | Kỳ vọng |
|---|---|---|---|---|
| `admin@demo-corp` | `tenant_admin` | — | GET `/admin/settings` | 200 |
| `admin@demo-corp` | `tenant_admin` | — | GET `/admin/users` | 200 |
| `cntt.cv@demo-corp` | `cntt_chuyenvien` | — | GET `/admin/users` | Trang 403 |
| `cntt.cv@demo-corp` | `cntt_chuyenvien` | — | GET `/cntt/templates` | 200 *(Phase 8+)* |
| `cntt.ld@demo-corp` | `cntt_lanhdao` | — | GET `/admin/users` | 200 |
| `cntt.ld@demo-corp` | `cntt_lanhdao` | — | GET `/admin/settings` | Trang 403 |
| `cntt.ld@demo-corp` | `cntt_lanhdao` | — | POST `/users` tạo `tenant_admin` | API 403 |
| `cntt.ld@demo-corp` | `cntt_lanhdao` | — | POST `/users/{cntt.cv}/dept-roles` | API 422 *(chỉ `dept_user`)* |
| `ketoan.cv@demo-corp` | `dept_user` | `KETOAN` / `chuyenvien` | `/auth/me` | `departments[]` có `KETOAN`, `chuyenvien` |
| `ketoan.cv@demo-corp` | `dept_user` | `KETOAN` / `chuyenvien` | Sidebar (Phase 4–7) | Tổng quan + Health *(menu `/dept/*` từ Phase 8+)* |
| `ketoan.ld@demo-corp` | `dept_user` | `KETOAN` / `lanhdao` | `has_capability(dept.approvals)` | `true` |
| `ketoan.cv@demo-corp` | `dept_user` | `KETOAN` / `chuyenvien` | `has_capability(dept.approvals)` | `false` |

---

### 11.5. Ghi chú triển khai tuần tự login

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

# Lấy fingerprint (step CLI ≥ 0.30 — không còn `step ca fingerprint`)
cat portal/docker/auth-test/pki/ca_fingerprint.txt
# hoặc:
docker exec portal-auth-step-ca step certificate fingerprint /home/step/certs/root_ca.crt
```

**Cấp cert client test** (cần cài [step CLI](https://smallstep.com/docs/step-cli/) trên máy dev):

```bash
chmod +x portal/docker/auth-test/scripts/issue-test-cert.sh
portal/docker/auth-test/scripts/issue-test-cert.sh cntt.cv
# Script tự đọc fingerprint từ ca_fingerprint.txt
```

**Import cert vào browser (Chrome):** Settings → Privacy → Security → Manage certificates → Import `cntt.cv.crt` + private key.

**Cấu hình PKI — dev (khuyến nghị — upload qua UI, §2.2):**

1. Đăng nhập `demo-corp` / `admin@demo-corp`
2. **Cài đặt tenant** → **Tải lên root CA** → chọn `portal/docker/auth-test/pki/root_ca.crt`
3. Bật `digital_signature_enabled` → Lưu

Hoặc qua API:

```bash
curl -b cookies.txt -X POST \
  "http://localhost:8000/tenants/{tenant_id}/settings/pki/ca-certificate" \
  -H "Content-Type: application/json" \
  -d "{\"certificate\": \"$(cat portal/docker/auth-test/pki/root_ca.crt | sed 's/\"/\\\"/g')\"}"
```

`pki_config` sau upload (PEM không trả về client):

```json
{
  "ca_certificate_uploaded": true,
  "ca_subject_dn": "CN=Portal Dev CA",
  "ca_fingerprint": "<sha256>",
  "ocsp_enabled": false,
  "require_cert_at_login": true,
  "require_cert_at_approval": true,
  "allowed_eku": ["clientAuth", "emailProtection"],
  "reject_expired": true,
  "reject_revoked": true
}
```

> **Legacy dev:** `trust_store_ref` + mount `PKI_ROOT_CA_PATH` vẫn hoạt động như fallback operator — không cần khi đã upload CA.

**Gate 3 — PKI:**

1. Upload `root_ca.crt` trên tenant demo (bước bắt buộc trước khi bật PKI)
2. Bật `digital_signature_enabled=true`
3. Login LDAP/OIDC/local → bước PKI hiện ra
4. Chọn cert `cntt.cv` (cấp bởi Step CA) → verify OK → `/auth/me` có `cert_serial`
5. Cert sai CA / hết hạn → 403
6. *(Tuỳ chọn)* Platform admin tạo tenant thứ 2 với CA khác → cert tenant A không verify trên tenant B

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

**Khuyến nghị:** Tenant admin upload full chain root/intermediate qua UI (§2.2) — không phụ thuộc mount Secret trên pod.

```json
{
  "ca_certificate_uploaded": true,
  "ca_subject_dn": "CN=Company Internal CA",
  "ca_fingerprint": "<sha256>",
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

**Fallback operator** (khi CA do DevOps quản lý tập trung, không qua UI):

```json
{
  "trust_store_ref": "k8s:portal/portal-pki#root_ca.pem"
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
0. Platform admin onboard tenant (POST /platform/tenants) + gán tenant_admin
1. Triển khai Portal Phase 1–11 (feature flag OFF) → smoke test local auth
2. Cấu hình Secret LDAP + test bind từ pod:
     kubectl -n portal exec -it deploy/portal -- ldapwhoami -H $LDAP_URI ...
3. Tenant admin bật sso_ldap_enabled trên tenant pilot → Gate 2 production
4. Tenant admin upload root_ca.crt (hoặc operator mount Secret PKI — fallback §2.2.4)
5. Pilot 5–10 user cài token → tenant admin bật digital_signature_enabled → Gate 3 production
6. Platform admin thêm tenant / tenant admin mở rộng user
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
│ Superset: [Đẩy SQL] [Bắt đầu thiết kế] [Đồng bộ dashboard] │
│ Dashboard liên kết: "X" (#id) hoặc chờ sync                │
├────────────────────────────────────────────┤
│ Preview table (100 rows max)               │
├────────────────────────────────────────────┤
│ Status: Draft ●  [Lưu nháp] [Gửi duyệt]   │
└────────────────────────────────────────────┘
```

**Approval Inbox LD CNTT:** Table + drawer: dashboard link, **[Mở trên Superset]**, SQL readonly, preview. **Duyệt** → ShareScopePicker modal (ALL / chọn PB) → provisioning RBAC.

**Dept templates (Phase 10):** Card mẫu + **[Xem trên Superset]** (standalone, không in/export UI).

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
| 4 | Admin dept/user tables, RoleRoute 403 |
| 7 | AI panel + SQL editor shell |
| 8 | Template Studio + Approval Inbox |
| 9 | ShareScopePicker modal |
| 10 | Transaction wizard + preview table |
| 11 | Approval Queue + Download Center |
| 12 | a11y audit, i18n complete, perf |

---

**Phiên bản:** 1.6  
**Cập nhật:** 2026-06-07  
**Trạng thái:** Phase 0–5 triển khai (Gate 5 provisioning). Workflow Superset-first: §1.3. Phân quyền: §11.1. UI: §14. Auth: §12. K8s: §13. Multi-tenant: §2.2.
