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
import type { SystemRole } from '@/api/auth';

export interface NavItem {
  key: string;
  labelKey: string;
  roles: SystemRole[] | 'all';
}

/** Sidebar navigation per §11.1 — Phase 1 shows allowed items only. */
export const NAV_ITEMS: NavItem[] = [
  { key: '/dashboard', labelKey: 'nav.overview', roles: 'all' },
  {
    key: '/admin/settings',
    labelKey: 'nav.tenantSettings',
    roles: ['tenant_admin'],
  },
  {
    key: '/admin/departments',
    labelKey: 'nav.departments',
    roles: ['tenant_admin', 'cntt_lanhdao'],
  },
  {
    key: '/admin/users',
    labelKey: 'nav.users',
    roles: ['tenant_admin', 'cntt_lanhdao'],
  },
  {
    key: '/cntt/templates',
    labelKey: 'nav.cnttTemplates',
    roles: ['cntt_chuyenvien', 'cntt_lanhdao'],
  },
  {
    key: '/cntt/approvals',
    labelKey: 'nav.cnttApprovals',
    roles: ['cntt_lanhdao'],
  },
  {
    key: '/dept/templates',
    labelKey: 'nav.deptTemplates',
    roles: ['dept_user'],
  },
  {
    key: '/dept/transactions',
    labelKey: 'nav.deptTransactions',
    roles: ['dept_user'],
  },
  {
    key: '/dept/approvals',
    labelKey: 'nav.deptApprovals',
    roles: ['dept_user'],
  },
  {
    key: '/audit',
    labelKey: 'nav.audit',
    roles: ['tenant_admin', 'cntt_lanhdao'],
  },
  { key: '/health-ui', labelKey: 'nav.health', roles: 'all' },
];

export function navItemsForRole(role: SystemRole): NavItem[] {
  return NAV_ITEMS.filter(
    (item) => item.roles === 'all' || item.roles.includes(role),
  );
}
