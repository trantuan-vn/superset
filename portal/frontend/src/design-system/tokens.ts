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
  colorPrimaryHover: string;
  colorPrimaryActive: string;
  colorSuccess: string;
  colorWarning: string;
  colorError: string;
  colorInfo: string;
  colorText: string;
  colorTextSecondary: string;
  colorTextTertiary: string;
  colorBorder: string;
  colorBorderSecondary: string;
  colorBgLayout: string;
  colorBgContainer: string;
  colorBgElevated: string;
  colorSidebar: string;
  colorSidebarActive: string;
  borderRadius: number;
  borderRadiusLg: number;
  fontFamily: string;
  fontSize: number;
  lineHeight: number;
  controlHeight: number;
  motionDurationMid: string;
  shadowSm: string;
  shadowMd: string;
  shadowLg: string;
}

export const defaultTokens: DesignTokens = {
  colorPrimary: '#2563eb',
  colorPrimaryHover: '#1d4ed8',
  colorPrimaryActive: '#1e40af',
  colorSuccess: '#16a34a',
  colorWarning: '#d97706',
  colorError: '#dc2626',
  colorInfo: '#2563eb',
  colorText: '#0f172a',
  colorTextSecondary: '#475569',
  colorTextTertiary: '#94a3b8',
  colorBorder: '#e2e8f0',
  colorBorderSecondary: '#f1f5f9',
  colorBgLayout: '#f8fafc',
  colorBgContainer: '#ffffff',
  colorBgElevated: '#ffffff',
  colorSidebar: '#ffffff',
  colorSidebarActive: '#eff6ff',
  borderRadius: 8,
  borderRadiusLg: 12,
  fontFamily:
    "'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  fontSize: 14,
  lineHeight: 1.5715,
  controlHeight: 40,
  motionDurationMid: '0.2s',
  shadowSm: '0 1px 2px rgba(15, 23, 42, 0.05)',
  shadowMd: '0 4px 12px rgba(15, 23, 42, 0.08)',
  shadowLg: '0 12px 32px rgba(15, 23, 42, 0.12)',
};

export const typography = {
  heading1: { fontSize: 30, fontWeight: 700, lineHeight: 1.25 },
  heading2: { fontSize: 24, fontWeight: 700, lineHeight: 1.3 },
  heading3: { fontSize: 18, fontWeight: 600, lineHeight: 1.4 },
  body: { fontSize: 14, fontWeight: 400, lineHeight: 1.5715 },
  caption: { fontSize: 12, fontWeight: 500, lineHeight: 1.5 },
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
  sidebarWidth: 260,
  sidebarCollapsedWidth: 72,
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
    colorPrimaryHover: branding.primary_color,
    colorPrimaryActive: branding.primary_color,
    colorSidebarActive: `${branding.primary_color}14`,
  };
}

export function tokensToCssVariables(tokens: DesignTokens): Record<string, string> {
  return {
    '--portal-primary': tokens.colorPrimary,
    '--portal-primary-hover': tokens.colorPrimaryHover,
    '--portal-text': tokens.colorText,
    '--portal-text-secondary': tokens.colorTextSecondary,
    '--portal-text-tertiary': tokens.colorTextTertiary,
    '--portal-border': tokens.colorBorder,
    '--portal-border-secondary': tokens.colorBorderSecondary,
    '--portal-bg-layout': tokens.colorBgLayout,
    '--portal-bg-container': tokens.colorBgContainer,
    '--portal-bg-elevated': tokens.colorBgElevated,
    '--portal-sidebar': tokens.colorSidebar,
    '--portal-sidebar-active': tokens.colorSidebarActive,
    '--portal-radius': `${tokens.borderRadius}px`,
    '--portal-radius-lg': `${tokens.borderRadiusLg}px`,
    '--portal-shadow-sm': tokens.shadowSm,
    '--portal-shadow-md': tokens.shadowMd,
    '--portal-shadow-lg': tokens.shadowLg,
    '--portal-font': tokens.fontFamily,
  };
}
