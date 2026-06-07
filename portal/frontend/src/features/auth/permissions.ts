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
import type { SystemRole, UserDeptRole } from '@/api/auth';

/** Mirrors backend Capability enum — SPEC §11.1 navigation matrix. */
export type Capability =
  | 'platform.tenants'
  | 'tenant.settings'
  | 'iam.admin'
  | 'cntt.templates'
  | 'cntt.approvals'
  | 'dept.templates'
  | 'dept.transactions'
  | 'dept.approvals'
  | 'audit.read';

export interface PermissionContext {
  systemRole: SystemRole;
  departments: UserDeptRole[];
}

const SYSTEM_ROLE_CAPABILITIES: Record<SystemRole, readonly Capability[]> = {
  platform_admin: ['platform.tenants'],
  tenant_admin: ['tenant.settings', 'iam.admin', 'audit.read'],
  cntt_lanhdao: [
    'iam.admin',
    'cntt.templates',
    'cntt.approvals',
    'audit.read',
  ],
  cntt_chuyenvien: ['cntt.templates'],
  dept_user: [],
};

const ROUTE_CAPABILITY: Record<string, Capability> = {
  '/platform/tenants': 'platform.tenants',
  '/admin/settings': 'tenant.settings',
  '/admin/departments': 'iam.admin',
  '/admin/users': 'iam.admin',
  '/cntt/templates': 'cntt.templates',
  '/cntt/approvals': 'cntt.approvals',
  '/dept/templates': 'dept.templates',
  '/dept/transactions': 'dept.transactions',
  '/dept/approvals': 'dept.approvals',
  '/audit': 'audit.read',
};

export function permissionContextFromUser(user: {
  system_role: SystemRole;
  departments?: UserDeptRole[];
}): PermissionContext {
  return {
    systemRole: user.system_role,
    departments: user.departments ?? [],
  };
}

export function hasDeptAssignment(ctx: PermissionContext): boolean {
  return ctx.departments.length > 0;
}

export function isDeptLeader(ctx: PermissionContext): boolean {
  return ctx.departments.some((d) => d.role === 'lanhdao');
}

export function isDeptSpecialist(ctx: PermissionContext): boolean {
  return ctx.departments.some((d) => d.role === 'chuyenvien');
}

export function hasCapability(
  ctx: PermissionContext,
  capability: Capability,
): boolean {
  const base = SYSTEM_ROLE_CAPABILITIES[ctx.systemRole] ?? [];
  if (base.includes(capability)) {
    return true;
  }

  if (ctx.systemRole !== 'dept_user') {
    return false;
  }

  if (!hasDeptAssignment(ctx)) {
    return false;
  }

  if (capability === 'dept.templates' || capability === 'dept.transactions') {
    return isDeptSpecialist(ctx) || isDeptLeader(ctx);
  }

  if (capability === 'dept.approvals') {
    return isDeptLeader(ctx);
  }

  return false;
}

export function routeCapability(path: string): Capability | null {
  const normalized = path.replace(/\/+$/, '') || '/';
  const match = Object.keys(ROUTE_CAPABILITY)
    .sort((a, b) => b.length - a.length)
    .find((prefix) => normalized === prefix || normalized.startsWith(`${prefix}/`));
  return match ? (ROUTE_CAPABILITY[match] ?? null) : null;
}

export function canAccessRoute(path: string, ctx: PermissionContext): boolean {
  const capability = routeCapability(path);
  if (!capability) {
    return true;
  }
  return hasCapability(ctx, capability);
}

/** Roles assignable via IAM UI — tenant_admin may assign all; others cannot assign tenant_admin. */
export function canAssignSystemRole(
  actor: PermissionContext,
  targetRole: SystemRole,
): boolean {
  if (targetRole === 'platform_admin') {
    return false;
  }
  if (targetRole === 'tenant_admin') {
    return actor.systemRole === 'tenant_admin';
  }
  return hasCapability(actor, 'iam.admin');
}

export function canModifyUser(
  actor: PermissionContext,
  target: { system_role: SystemRole },
): boolean {
  if (!hasCapability(actor, 'iam.admin')) {
    return false;
  }
  if (target.system_role === 'platform_admin') {
    return false;
  }
  if (
    target.system_role === 'tenant_admin' &&
    actor.systemRole !== 'tenant_admin'
  ) {
    return false;
  }
  return true;
}
