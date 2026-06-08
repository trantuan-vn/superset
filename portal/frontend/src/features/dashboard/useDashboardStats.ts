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
import { useQueries } from '@tanstack/react-query';
import { useMemo } from 'react';

import type { AuthUser } from '@/api/auth';
import { fetchDepartments } from '@/api/departments';
import { fetchPlatformTenants } from '@/api/platform';
import { fetchTemplates } from '@/api/templates';
import {
  fetchDeptTemplates,
  fetchMyTransactions,
  fetchPendingTransactions,
} from '@/api/transactions';
import { fetchUsers } from '@/api/users';
import {
  hasCapability,
  hasDeptAssignment,
  isDeptLeader,
  isDeptSpecialist,
  permissionContextFromUser,
  type PermissionContext,
} from '@/features/auth/permissions';

export type DashboardProfile =
  | 'platform_admin'
  | 'tenant_admin'
  | 'cntt_chuyenvien'
  | 'cntt_lanhdao'
  | 'dept_chuyenvien'
  | 'dept_lanhdao'
  | 'dept_unassigned';

export interface DashboardStat {
  key: string;
  titleKey: string;
  value: number;
  link?: string;
}

export interface DashboardQuickLink {
  key: string;
  labelKey: string;
  path: string;
}

export function resolveDashboardProfile(user: AuthUser): DashboardProfile {
  if (user.system_role === 'dept_user') {
    const ctx = permissionContextFromUser(user);
    if (!hasDeptAssignment(ctx)) {
      return 'dept_unassigned';
    }
    if (isDeptLeader(ctx)) {
      return 'dept_lanhdao';
    }
    if (isDeptSpecialist(ctx)) {
      return 'dept_chuyenvien';
    }
    return 'dept_unassigned';
  }
  return user.system_role;
}

function quickLinksForProfile(
  profile: DashboardProfile,
  ctx: PermissionContext,
): DashboardQuickLink[] {
  const links: DashboardQuickLink[] = [];

  if (profile === 'platform_admin') {
    links.push({
      key: 'tenants',
      labelKey: 'dashboard.links.tenants',
      path: '/platform/tenants',
    });
  }

  if (profile === 'tenant_admin') {
    links.push(
      {
        key: 'departments',
        labelKey: 'dashboard.links.departments',
        path: '/admin/departments',
      },
      {
        key: 'users',
        labelKey: 'dashboard.links.users',
        path: '/admin/users',
      },
      {
        key: 'settings',
        labelKey: 'dashboard.links.settings',
        path: '/admin/settings',
      },
    );
  }

  if (profile === 'cntt_chuyenvien' || profile === 'cntt_lanhdao') {
    links.push({
      key: 'templates',
      labelKey: 'dashboard.links.templates',
      path: '/cntt/templates',
    });
  }

  if (profile === 'cntt_lanhdao') {
    links.push({
      key: 'approvals',
      labelKey: 'dashboard.links.cnttApprovals',
      path: '/cntt/approvals',
    });
  }

  if (profile === 'cntt_lanhdao' && hasCapability(ctx, 'iam.admin')) {
    links.push({
      key: 'users',
      labelKey: 'dashboard.links.users',
      path: '/admin/users',
    });
  }

  if (profile === 'dept_chuyenvien' || profile === 'dept_lanhdao') {
    links.push({
      key: 'deptTemplates',
      labelKey: 'dashboard.links.deptTemplates',
      path: '/dept/templates',
    });
  }

  if (profile === 'dept_chuyenvien') {
    links.push({
      key: 'transactions',
      labelKey: 'dashboard.links.transactions',
      path: '/dept/transactions',
    });
  }

  if (profile === 'dept_lanhdao') {
    links.push({
      key: 'deptApprovals',
      labelKey: 'dashboard.links.deptApprovals',
      path: '/dept/approvals',
    });
  }

  return links;
}

export function useDashboardStats(user: AuthUser | null | undefined) {
  const ctx = user ? permissionContextFromUser(user) : null;
  const profile = user ? resolveDashboardProfile(user) : null;

  const queryResults = useQueries({
    queries: [
      {
        queryKey: ['dashboard', 'platform-tenants'],
        queryFn: fetchPlatformTenants,
        enabled: profile === 'platform_admin',
      },
      {
        queryKey: ['dashboard', 'departments'],
        queryFn: () => fetchDepartments(),
        enabled: profile === 'tenant_admin',
      },
      {
        queryKey: ['dashboard', 'users'],
        queryFn: () => fetchUsers(),
        enabled: profile === 'tenant_admin',
      },
      {
        queryKey: ['dashboard', 'cntt-templates'],
        queryFn: () => fetchTemplates(),
        enabled: profile === 'cntt_chuyenvien' || profile === 'cntt_lanhdao',
      },
      {
        queryKey: ['dashboard', 'cntt-pending'],
        queryFn: () => fetchTemplates({ pending: true }),
        enabled: profile === 'cntt_lanhdao',
      },
      {
        queryKey: ['dashboard', 'dept-templates'],
        queryFn: fetchDeptTemplates,
        enabled: profile === 'dept_chuyenvien' || profile === 'dept_lanhdao',
      },
      {
        queryKey: ['dashboard', 'my-transactions'],
        queryFn: fetchMyTransactions,
        enabled: profile === 'dept_chuyenvien',
      },
      {
        queryKey: ['dashboard', 'pending-transactions'],
        queryFn: fetchPendingTransactions,
        enabled: profile === 'dept_lanhdao',
      },
    ],
  });

  const [
    platformTenantsQuery,
    departmentsQuery,
    usersQuery,
    cnttTemplatesQuery,
    cnttPendingQuery,
    deptTemplatesQuery,
    myTransactionsQuery,
    pendingTransactionsQuery,
  ] = queryResults;

  const stats = useMemo((): DashboardStat[] => {
    if (!profile) {
      return [];
    }

    switch (profile) {
      case 'platform_admin': {
        const tenants = platformTenantsQuery.data ?? [];
        const active = tenants.filter((t) => t.status === 'active').length;
        return [
          {
            key: 'tenants',
            titleKey: 'dashboard.stats.tenants',
            value: tenants.length,
            link: '/platform/tenants',
          },
          {
            key: 'activeTenants',
            titleKey: 'dashboard.stats.activeTenants',
            value: active,
            link: '/platform/tenants',
          },
        ];
      }
      case 'tenant_admin': {
        const departments = departmentsQuery.data ?? [];
        const users = usersQuery.data ?? [];
        const activeUsers = users.filter((u) => u.status === 'active').length;
        return [
          {
            key: 'departments',
            titleKey: 'dashboard.stats.departments',
            value: departments.filter((d) => d.status === 'active').length,
            link: '/admin/departments',
          },
          {
            key: 'users',
            titleKey: 'dashboard.stats.users',
            value: users.length,
            link: '/admin/users',
          },
          {
            key: 'activeUsers',
            titleKey: 'dashboard.stats.activeUsers',
            value: activeUsers,
            link: '/admin/users',
          },
        ];
      }
      case 'cntt_chuyenvien': {
        const templates = cnttTemplatesQuery.data ?? [];
        return [
          {
            key: 'templates',
            titleKey: 'dashboard.stats.templates',
            value: templates.length,
            link: '/cntt/templates',
          },
          {
            key: 'draftTemplates',
            titleKey: 'dashboard.stats.draftTemplates',
            value: templates.filter((t) => t.status === 'draft').length,
            link: '/cntt/templates',
          },
          {
            key: 'inReview',
            titleKey: 'dashboard.stats.inReview',
            value: templates.filter((t) => t.status === 'review').length,
            link: '/cntt/templates',
          },
        ];
      }
      case 'cntt_lanhdao': {
        const templates = cnttTemplatesQuery.data ?? [];
        const pending = cnttPendingQuery.data ?? [];
        return [
          {
            key: 'pendingApprovals',
            titleKey: 'dashboard.stats.pendingApprovals',
            value: pending.length,
            link: '/cntt/approvals',
          },
          {
            key: 'publishedTemplates',
            titleKey: 'dashboard.stats.publishedTemplates',
            value: templates.filter((t) => t.status === 'published').length,
            link: '/cntt/templates',
          },
          {
            key: 'inReview',
            titleKey: 'dashboard.stats.inReview',
            value: templates.filter((t) => t.status === 'review').length,
            link: '/cntt/approvals',
          },
        ];
      }
      case 'dept_chuyenvien': {
        const templates = deptTemplatesQuery.data ?? [];
        const transactions = myTransactionsQuery.data ?? [];
        return [
          {
            key: 'availableTemplates',
            titleKey: 'dashboard.stats.availableTemplates',
            value: templates.length,
            link: '/dept/templates',
          },
          {
            key: 'pendingTransactions',
            titleKey: 'dashboard.stats.pendingTransactions',
            value: transactions.filter((t) => t.status === 'submitted').length,
            link: '/dept/transactions',
          },
          {
            key: 'draftTransactions',
            titleKey: 'dashboard.stats.draftTransactions',
            value: transactions.filter((t) => t.status === 'draft').length,
            link: '/dept/transactions',
          },
        ];
      }
      case 'dept_lanhdao': {
        const templates = deptTemplatesQuery.data ?? [];
        const pending = pendingTransactionsQuery.data ?? [];
        return [
          {
            key: 'pendingApprovals',
            titleKey: 'dashboard.stats.pendingApprovals',
            value: pending.length,
            link: '/dept/approvals',
          },
          {
            key: 'availableTemplates',
            titleKey: 'dashboard.stats.availableTemplates',
            value: templates.length,
            link: '/dept/templates',
          },
        ];
      }
      default:
        return [];
    }
  }, [
    profile,
    platformTenantsQuery.data,
    departmentsQuery.data,
    usersQuery.data,
    cnttTemplatesQuery.data,
    cnttPendingQuery.data,
    deptTemplatesQuery.data,
    myTransactionsQuery.data,
    pendingTransactionsQuery.data,
  ]);

  const quickLinks = useMemo(
    () => (profile && ctx ? quickLinksForProfile(profile, ctx) : []),
    [profile, ctx],
  );

  const isLoading =
    profile !== 'dept_unassigned' &&
    queryResults.some((q) => q.isEnabled && q.isLoading);

  const error = queryResults.find((q) => q.isEnabled && q.isError)?.error;

  return { profile, stats, quickLinks, isLoading, error };
}
