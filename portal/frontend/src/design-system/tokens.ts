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
/** Design tokens — §14.2 / §14.3. Tenant branding overrides at runtime. */

export interface DesignTokens {
  colorPrimary: string;
  colorSuccess: string;
  colorWarning: string;
  colorError: string;
  colorInfo: string;
  borderRadius: number;
  fontFamily: string;
  fontSize: number;
  lineHeight: number;
  controlHeight: number;
  motionDurationMid: string;
}

export const defaultTokens: DesignTokens = {
  colorPrimary: '#1677ff',
  colorSuccess: '#52c41a',
  colorWarning: '#faad14',
  colorError: '#ff4d4f',
  colorInfo: '#1677ff',
  borderRadius: 8,
  fontFamily:
    "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  fontSize: 14,
  lineHeight: 1.5715,
  controlHeight: 40,
  motionDurationMid: '0.2s',
};

export const typography = {
  heading1: { fontSize: 30, fontWeight: 600, lineHeight: 1.25 },
  heading2: { fontSize: 24, fontWeight: 600, lineHeight: 1.3 },
  heading3: { fontSize: 18, fontWeight: 600, lineHeight: 1.4 },
  body: { fontSize: 14, fontWeight: 400, lineHeight: 1.5715 },
  caption: { fontSize: 12, fontWeight: 400, lineHeight: 1.5 },
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
  xxxl: 48,
} as const;

export const layout = {
  sidebarWidth: 240,
  sidebarCollapsedWidth: 64,
  contentMaxWidth: 1440,
  contentPadding: 24,
  headerHeight: 64,
  breakpointTablet: 768,
  breakpointDesktop: 1280,
} as const;

export interface TenantBranding {
  app_name?: string;
  logo_url?: string;
  primary_color?: string;
  favicon_url?: string;
}

export function mergeBrandingTokens(
  branding?: TenantBranding | null,
): DesignTokens {
  if (!branding?.primary_color) {
    return defaultTokens;
  }
  return {
    ...defaultTokens,
    colorPrimary: branding.primary_color,
    colorInfo: branding.primary_color,
  };
}
