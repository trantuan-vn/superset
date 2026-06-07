/**
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */

const API_BASE = import.meta.env.VITE_API_URL ?? '';

export type SystemRole =
  | 'platform_admin'
  | 'tenant_admin'
  | 'cntt_chuyenvien'
  | 'cntt_lanhdao'
  | 'dept_user';

export interface TenantBranding {
  app_name?: string;
  logo_url?: string;
  primary_color?: string;
  favicon_url?: string;
}

export interface UserDeptRole {
  department_id: string;
  department_code: string;
  department_name: string;
  role: 'chuyenvien' | 'lanhdao';
}

export interface AuthUser {
  id: string;
  username: string;
  email: string;
  display_name: string;
  system_role: SystemRole;
  departments?: UserDeptRole[];
}

export interface AuthTenant {
  id: string;
  slug: string;
  name: string;
  ai_enabled?: boolean;
  branding?: TenantBranding | null;
}

export interface MeResponse {
  user: AuthUser;
  tenant: AuthTenant;
  pki_pending?: boolean;
  cert_serial?: string | null;
}

export interface PkiChallengeResponse {
  nonce: string;
  expires_in_seconds: number;
}

export interface PkiVerifyPayload {
  certificate: string;
  signature: string;
}

export interface PkiVerifyResponse {
  cert_serial: string;
  subject_dn: string;
  message: string;
}

export interface LoginPayload {
  tenant_slug: string;
  username: string;
  password: string;
}

export interface LoginOptions {
  tenant_slug: string;
  tenant_name: string;
  sso_enabled: boolean;
  auth_mode: 'local' | 'oidc' | 'saml' | 'ldap';
  sso_primary: boolean;
  show_local_login: boolean;
  pki_enabled?: boolean;
  branding?: TenantBranding | null;
}

class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function parseError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string };
    return body.detail ?? response.statusText;
  } catch {
    return response.statusText;
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!response.ok) {
    throw new ApiError(await parseError(response), response.status);
  }
  return response.json() as Promise<T>;
}

export async function login(payload: LoginPayload): Promise<MeResponse> {
  return apiFetch<MeResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function logout(): Promise<void> {
  await apiFetch<{ message: string }>('/auth/logout', { method: 'POST' });
}

export async function fetchMe(): Promise<MeResponse> {
  return apiFetch<MeResponse>('/auth/me');
}

export async function fetchLoginOptions(
  tenantSlug: string,
): Promise<LoginOptions> {
  const params = new URLSearchParams({ tenant_slug: tenantSlug });
  return apiFetch<LoginOptions>(`/auth/login-options?${params.toString()}`);
}

/** Full URL to start OIDC SSO (browser navigation). */
export function ssoLoginUrl(tenantSlug: string): string {
  const base = API_BASE || '';
  const params = new URLSearchParams({ tenant_slug: tenantSlug });
  return `${base}/auth/sso/login?${params.toString()}`;
}

export async function fetchPkiChallenge(): Promise<PkiChallengeResponse> {
  return apiFetch<PkiChallengeResponse>('/auth/pki/challenge', {
    method: 'POST',
  });
}

export async function verifyPki(
  payload: PkiVerifyPayload,
): Promise<PkiVerifyResponse> {
  return apiFetch<PkiVerifyResponse>('/auth/pki/verify', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export { ApiError, apiFetch };
