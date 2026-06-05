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
      borderRadius: tokens.borderRadius,
      fontFamily: tokens.fontFamily,
      fontSize: tokens.fontSize,
      lineHeight: tokens.lineHeight,
      controlHeight: tokens.controlHeight,
      motionDurationMid: tokens.motionDurationMid,
    },
    components: {
      Layout: {
        headerBg: '#ffffff',
        siderBg: '#001529',
        bodyBg: '#f5f7fa',
      },
      Menu: {
        darkItemBg: '#001529',
      },
    },
  };
}

export const defaultTheme = createAntdTheme();
