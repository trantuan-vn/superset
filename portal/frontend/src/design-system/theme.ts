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
import type { ThemeConfig } from 'antd';

import { mergeBrandingTokens, type TenantBranding } from './tokens';

export function createAntdTheme(branding?: TenantBranding | null): ThemeConfig {
  const tokens = mergeBrandingTokens(branding);

  return {
    token: {
      colorPrimary: tokens.colorPrimary,
      colorSuccess: tokens.colorSuccess,
      colorWarning: tokens.colorWarning,
      colorError: tokens.colorError,
      colorInfo: tokens.colorInfo,
      colorText: tokens.colorText,
      colorTextSecondary: tokens.colorTextSecondary,
      colorTextTertiary: tokens.colorTextTertiary,
      colorBorder: tokens.colorBorder,
      colorBorderSecondary: tokens.colorBorderSecondary,
      colorBgLayout: tokens.colorBgLayout,
      colorBgContainer: tokens.colorBgContainer,
      colorBgElevated: tokens.colorBgElevated,
      borderRadius: tokens.borderRadius,
      borderRadiusLG: tokens.borderRadiusLg,
      fontFamily: tokens.fontFamily,
      fontSize: tokens.fontSize,
      lineHeight: tokens.lineHeight,
      controlHeight: tokens.controlHeight,
      motionDurationMid: tokens.motionDurationMid,
      boxShadow: tokens.shadowMd,
      boxShadowSecondary: tokens.shadowSm,
    },
    components: {
      Layout: {
        headerBg: tokens.colorBgContainer,
        siderBg: tokens.colorSidebar,
        bodyBg: tokens.colorBgLayout,
        headerHeight: 64,
        headerPadding: '0 24px',
      },
      Menu: {
        itemBg: 'transparent',
        itemColor: tokens.colorTextSecondary,
        itemHoverColor: tokens.colorText,
        itemHoverBg: tokens.colorBorderSecondary,
        itemSelectedColor: tokens.colorPrimary,
        itemSelectedBg: tokens.colorSidebarActive,
        itemActiveBg: tokens.colorSidebarActive,
        iconSize: 18,
        itemHeight: 44,
        itemBorderRadius: tokens.borderRadius,
        groupTitleColor: tokens.colorTextTertiary,
        activeBarBorderWidth: 0,
      },
      Card: {
        borderRadiusLG: tokens.borderRadiusLg,
        boxShadowTertiary: tokens.shadowSm,
        headerFontSize: 16,
        paddingLG: 24,
      },
      Button: {
        borderRadius: tokens.borderRadius,
        controlHeight: tokens.controlHeight,
        fontWeight: 600,
        primaryShadow: 'none',
        defaultShadow: 'none',
      },
      Table: {
        headerBg: tokens.colorBorderSecondary,
        headerColor: tokens.colorTextSecondary,
        borderColor: tokens.colorBorder,
        rowHoverBg: tokens.colorBorderSecondary,
      },
      Input: {
        borderRadius: tokens.borderRadius,
        controlHeight: tokens.controlHeight,
      },
      Select: {
        borderRadius: tokens.borderRadius,
        controlHeight: tokens.controlHeight,
      },
      Tag: {
        borderRadiusSM: 6,
      },
      Breadcrumb: {
        itemColor: tokens.colorTextTertiary,
        lastItemColor: tokens.colorTextSecondary,
        linkColor: tokens.colorTextTertiary,
        linkHoverColor: tokens.colorPrimary,
      },
      Statistic: {
        titleFontSize: 13,
        contentFontSize: 28,
      },
    },
  };
}

export const defaultTheme = createAntdTheme();
