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

import { apiFetch } from '@/api/auth';
import type { ProvisioningSummary } from '@/api/provisioning';

export type DepartmentStatus = 'active' | 'inactive';

export interface Department {
  id: string;
  tenant_id: string;
  code: string;
  name: string;
  status: DepartmentStatus;
  provisioning?: ProvisioningSummary | null;
}

export interface CreateDepartmentPayload {
  code: string;
  name: string;
}

export interface UpdateDepartmentPayload {
  name?: string;
  status?: DepartmentStatus;
}

export async function fetchDepartments(params?: {
  search?: string;
  status?: DepartmentStatus;
}): Promise<Department[]> {
  const query = new URLSearchParams();
  if (params?.search) {
    query.set('search', params.search);
  }
  if (params?.status) {
    query.set('status', params.status);
  }
  const suffix = query.toString() ? `?${query.toString()}` : '';
  return apiFetch<Department[]>(`/departments${suffix}`);
}

export async function createDepartment(
  payload: CreateDepartmentPayload,
): Promise<Department> {
  return apiFetch<Department>('/departments', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateDepartment(
  id: string,
  payload: UpdateDepartmentPayload,
): Promise<Department> {
  return apiFetch<Department>(`/departments/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}
