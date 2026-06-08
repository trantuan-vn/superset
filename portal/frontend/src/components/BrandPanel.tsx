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
import {
  AuditOutlined,
  CloudServerOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons';
import { Typography } from 'antd';
import { useTranslation } from 'react-i18next';

import { PortalLogo } from '@/components/PortalLogo';

import styles from './BrandPanel.module.css';

interface BrandPanelProps {
  appName?: string;
  primaryColor?: string;
  logoUrl?: string;
}

const FEATURE_KEYS = ['security', 'workflow', 'enterprise'] as const;

const FEATURE_ICONS = {
  security: SafetyCertificateOutlined,
  workflow: AuditOutlined,
  enterprise: CloudServerOutlined,
} as const;

export function BrandPanel({ appName, primaryColor, logoUrl }: BrandPanelProps) {
  const { t } = useTranslation();
  const title = appName ?? t('app.name');

  return (
    <section className={styles.panel} aria-hidden={false}>
      <div className={styles.backgroundPattern} aria-hidden />
      <div className={styles.content}>
        <div className={styles.logoRow}>
          {logoUrl ? (
            <img src={logoUrl} alt="" className={styles.logoImage} />
          ) : (
            <PortalLogo size="lg" accentColor={primaryColor} className={styles.logoMark} />
          )}
          <div>
            <Typography.Title level={2} className={styles.title}>
              {title}
            </Typography.Title>
            <Typography.Paragraph className={styles.tagline}>
              {t('app.tagline')}
            </Typography.Paragraph>
          </div>
        </div>

        <ul className={styles.features}>
          {FEATURE_KEYS.map((key) => {
            const Icon = FEATURE_ICONS[key];
            return (
              <li key={key} className={styles.featureItem}>
                <span className={styles.featureIcon} aria-hidden>
                  <Icon />
                </span>
                <div>
                  <strong>{t(`auth.features.${key}.title`)}</strong>
                  <p>{t(`auth.features.${key}.desc`)}</p>
                </div>
              </li>
            );
          })}
        </ul>

        <p className={styles.trustNote}>{t('auth.trustNote')}</p>
      </div>
    </section>
  );
}
