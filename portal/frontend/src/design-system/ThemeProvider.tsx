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
import { ConfigProvider } from 'antd';
import viVN from 'antd/locale/vi_VN';
import { useMemo, type CSSProperties, type ReactNode } from 'react';

import { useAuth } from '@/features/auth/useAuth';
import { createAntdTheme } from '@/design-system/theme';
import {
  mergeBrandingTokens,
  tokensToCssVariables,
  type TenantBranding,
} from '@/design-system/tokens';

interface ThemeProviderProps {
  children: ReactNode;
  branding?: TenantBranding | null;
}

export function ThemeProvider({ children, branding }: ThemeProviderProps) {
  const theme = useMemo(() => createAntdTheme(branding), [branding]);
  const cssVars = useMemo(
    () => tokensToCssVariables(mergeBrandingTokens(branding)),
    [branding],
  );

  return (
    <ConfigProvider theme={theme} locale={viVN}>
      <div style={cssVars as CSSProperties}>{children}</div>
    </ConfigProvider>
  );
}

export function TenantThemeProvider({ children }: { children: ReactNode }) {
  const { tenant } = useAuth();
  return (
    <ThemeProvider branding={tenant?.branding}>{children}</ThemeProvider>
  );
}
