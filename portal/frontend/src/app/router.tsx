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
import { createBrowserRouter, Navigate } from 'react-router-dom';

import { AppShell } from '@/app/AppShell';
import { ProtectedRoute } from '@/features/auth/ProtectedRoute';
import { RoleRoute } from '@/features/auth/RoleRoute';
import { AdminDepartmentsPage } from '@/pages/AdminDepartmentsPage';
import { AdminSettingsPage } from '@/pages/AdminSettingsPage';
import { AdminUsersPage } from '@/pages/AdminUsersPage';
import { PlatformTenantsPage } from '@/pages/PlatformTenantsPage';
import { TemplateStudioPage } from '@/features/templates/TemplateStudioPage';
import { CnttApprovalsPage } from '@/pages/CnttApprovalsPage';
import { CnttTemplatesPage } from '@/pages/CnttTemplatesPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { HealthUiPage } from '@/pages/HealthUiPage';
import { LoginPage } from '@/pages/LoginPage';
import { PkiVerifyPage } from '@/pages/PkiVerifyPage';

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/login/pki', element: <PkiVerifyPage /> },
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <AppShell />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: 'dashboard', element: <DashboardPage /> },
      {
        path: 'admin/settings',
        element: (
          <RoleRoute route="/admin/settings">
            <AdminSettingsPage />
          </RoleRoute>
        ),
      },
      {
        path: 'admin/departments',
        element: (
          <RoleRoute route="/admin/departments">
            <AdminDepartmentsPage />
          </RoleRoute>
        ),
      },
      {
        path: 'admin/users',
        element: (
          <RoleRoute route="/admin/users">
            <AdminUsersPage />
          </RoleRoute>
        ),
      },
      {
        path: 'platform/tenants',
        element: (
          <RoleRoute route="/platform/tenants">
            <PlatformTenantsPage />
          </RoleRoute>
        ),
      },
      {
        path: 'cntt/templates',
        element: (
          <RoleRoute route="/cntt/templates">
            <CnttTemplatesPage />
          </RoleRoute>
        ),
      },
      {
        path: 'cntt/templates/:id',
        element: (
          <RoleRoute route="/cntt/templates">
            <TemplateStudioPage />
          </RoleRoute>
        ),
      },
      {
        path: 'cntt/approvals',
        element: (
          <RoleRoute route="/cntt/approvals">
            <CnttApprovalsPage />
          </RoleRoute>
        ),
      },
      { path: 'health-ui', element: <HealthUiPage /> },
    ],
  },
  { path: '*', element: <Navigate to="/dashboard" replace /> },
]);
