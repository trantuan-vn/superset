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
import type { ReactNode } from 'react';

import { ForbiddenPage } from '@/pages/ForbiddenPage';
import {
  canAccessRoute,
  permissionContextFromUser,
} from '@/features/auth/permissions';
import { useAuth } from '@/features/auth/useAuth';

interface RoleRouteProps {
  /** Route path used for capability lookup (e.g. `/admin/users`). */
  route: string;
  children: ReactNode;
}

/** Route guard — SPEC §11.1 role × department matrix. */
export function RoleRoute({ route, children }: RoleRouteProps) {
  const { user } = useAuth();

  if (!user) {
    return null;
  }

  const ctx = permissionContextFromUser(user);
  if (!canAccessRoute(route, ctx)) {
    return <ForbiddenPage />;
  }

  return children;
}
