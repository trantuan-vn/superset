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
import type { AuthUser } from '@/api/auth';
import {
  canAccessRoute,
  permissionContextFromUser,
} from '@/features/auth/permissions';

export interface NavItem {
  key: string;
  labelKey: string;
}

/** Sidebar navigation entries — visibility resolved via permissions (SPEC §11.1). */
export const NAV_ITEMS: NavItem[] = [
  { key: '/dashboard', labelKey: 'nav.overview' },
  { key: '/platform/tenants', labelKey: 'nav.platformTenants' },
  { key: '/admin/settings', labelKey: 'nav.tenantSettings' },
  { key: '/admin/departments', labelKey: 'nav.departments' },
  { key: '/admin/users', labelKey: 'nav.users' },
  { key: '/cntt/templates', labelKey: 'nav.cnttTemplates' },
  { key: '/cntt/approvals', labelKey: 'nav.cnttApprovals' },
  { key: '/dept/templates', labelKey: 'nav.deptTemplates' },
  { key: '/dept/transactions', labelKey: 'nav.deptTransactions' },
  { key: '/dept/approvals', labelKey: 'nav.deptApprovals' },
  { key: '/audit', labelKey: 'nav.audit' },
  { key: '/health-ui', labelKey: 'nav.health' },
];

export function navItemsForUser(user: AuthUser): NavItem[] {
  const ctx = permissionContextFromUser(user);
  return NAV_ITEMS.filter((item) => canAccessRoute(item.key, ctx));
}
