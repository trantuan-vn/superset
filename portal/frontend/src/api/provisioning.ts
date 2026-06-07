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

export type ProvisioningSyncStatus =
  | 'pending'
  | 'success'
  | 'failed'
  | 'dead_letter'
  | 'skipped';

export interface ProvisioningSummary {
  status: ProvisioningSyncStatus;
  message?: string | null;
}

export interface ProvisioningLog {
  id: string;
  entity_type: string;
  entity_key: string;
  operation: string;
  superset_id: number | null;
  status: ProvisioningSyncStatus;
  error_message: string | null;
  attempts: number;
  updated_at: string;
}

export interface ProvisioningStatus {
  enabled: boolean;
  superset_reachable: boolean;
  logs: ProvisioningLog[];
}

export async function fetchProvisioningStatus(
  entityKey?: string,
): Promise<ProvisioningStatus> {
  const query = entityKey ? `?entity_key=${encodeURIComponent(entityKey)}` : '';
  return apiFetch<ProvisioningStatus>(`/provisioning/status${query}`);
}

export async function retryProvisioning(): Promise<{ message: string }> {
  return apiFetch<{ message: string }>('/provisioning/retry', { method: 'POST' });
}
