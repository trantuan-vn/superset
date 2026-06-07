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

import { apiFetch, type SystemRole, type UserDeptRole } from '@/api/auth';

export type UserStatus = 'active' | 'inactive' | 'locked';
export type DeptRole = 'chuyenvien' | 'lanhdao';

export interface PortalUser {
  id: string;
  username: string;
  email: string;
  display_name: string;
  system_role: SystemRole;
  status: UserStatus;
  departments: UserDeptRole[];
}

export interface CreateUserPayload {
  username: string;
  email: string;
  display_name: string;
  password: string;
  system_role: SystemRole;
}

export interface UpdateUserPayload {
  display_name?: string;
  email?: string;
  status?: UserStatus;
}

export interface AssignDeptRolePayload {
  department_id: string;
  role: DeptRole;
}

export async function fetchUsers(params?: {
  search?: string;
  system_role?: SystemRole;
}): Promise<PortalUser[]> {
  const query = new URLSearchParams();
  if (params?.search) {
    query.set('search', params.search);
  }
  if (params?.system_role) {
    query.set('system_role', params.system_role);
  }
  const suffix = query.toString() ? `?${query.toString()}` : '';
  return apiFetch<PortalUser[]>(`/users${suffix}`);
}

export async function createUser(payload: CreateUserPayload): Promise<PortalUser> {
  return apiFetch<PortalUser>('/users', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateUser(
  id: string,
  payload: UpdateUserPayload,
): Promise<PortalUser> {
  return apiFetch<PortalUser>(`/users/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function assignDeptRole(
  userId: string,
  payload: AssignDeptRolePayload,
): Promise<PortalUser> {
  return apiFetch<PortalUser>(`/users/${userId}/dept-roles`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function removeDeptRole(
  userId: string,
  departmentId: string,
): Promise<void> {
  await apiFetch<{ message: string }>(
    `/users/${userId}/dept-roles/${departmentId}`,
    { method: 'DELETE' },
  );
}
