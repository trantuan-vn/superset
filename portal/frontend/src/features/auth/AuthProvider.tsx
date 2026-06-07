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
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { message } from 'antd';
import { useCallback, useEffect, useMemo, useRef, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import {
  ApiError,
  fetchMe,
  login as apiLogin,
  logout as apiLogout,
} from '@/api/auth';
import { AuthContext, type AuthContextValue } from '@/features/auth/authContext';

const AUTH_QUERY_KEY = ['auth', 'me'] as const;

export function AuthProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: AUTH_QUERY_KEY,
    queryFn: fetchMe,
    retry: false,
    staleTime: 60_000,
  });

  const sessionExpiredShown = useRef(false);

  useEffect(() => {
    const sessionExpired =
      isError && error instanceof ApiError && error.status === 401;
    if (sessionExpired && !sessionExpiredShown.current) {
      sessionExpiredShown.current = true;
      message.warning(t('auth.sessionExpired'));
    }
    if (!sessionExpired) {
      sessionExpiredShown.current = false;
    }
  }, [isError, error, t]);

  const login = useCallback(
    async (payload: Parameters<typeof apiLogin>[0]) => {
      const result = await apiLogin(payload);
      queryClient.setQueryData(AUTH_QUERY_KEY, result);
      return result;
    },
    [queryClient],
  );

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } finally {
      queryClient.setQueryData(AUTH_QUERY_KEY, null);
      queryClient.removeQueries({ queryKey: AUTH_QUERY_KEY });
    }
  }, [queryClient]);

  const refresh = useCallback(async () => {
    await refetch();
  }, [refetch]);

  const pkiPending = Boolean(data?.pki_pending);
  const isFullyAuthenticated = Boolean(data?.user) && !pkiPending;

  const value = useMemo<AuthContextValue>(
    () => ({
      user: data?.user ?? null,
      tenant: data?.tenant ?? null,
      isLoading,
      isAuthenticated: isFullyAuthenticated,
      pkiPending,
      certSerial: data?.cert_serial ?? null,
      login,
      logout,
      refresh,
    }),
    [data, isLoading, isFullyAuthenticated, pkiPending, login, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
