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
  ArrowRightOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  FileTextOutlined,
  SwapOutlined,
  TeamOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { Alert, Col, Row, Tag, Typography } from 'antd';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import { LoadingSkeleton } from '@/components/LoadingSkeleton';
import { PageHeader } from '@/components/PageHeader';
import { StatCard } from '@/components/StatCard';
import {
  resolveDashboardProfile,
  useDashboardStats,
} from '@/features/dashboard/useDashboardStats';
import { useAuth } from '@/features/auth/useAuth';

import styles from './DashboardPage.module.css';

const STAT_ICONS: Record<string, ReactNode> = {
  tenants: <TeamOutlined />,
  activeTenants: <CheckCircleOutlined />,
  departments: <TeamOutlined />,
  users: <UserOutlined />,
  activeUsers: <CheckCircleOutlined />,
  templates: <FileTextOutlined />,
  draftTemplates: <FileTextOutlined />,
  inReview: <ClockCircleOutlined />,
  pendingApprovals: <ClockCircleOutlined />,
  publishedTemplates: <CheckCircleOutlined />,
  availableTemplates: <FileTextOutlined />,
  myTransactions: <SwapOutlined />,
  pendingTransactions: <ClockCircleOutlined />,
  draftTransactions: <FileTextOutlined />,
  completedTransactions: <CheckCircleOutlined />,
};

const STAT_ACCENTS: Record<string, 'blue' | 'green' | 'amber' | 'slate'> = {
  pendingApprovals: 'amber',
  pendingTransactions: 'amber',
  inReview: 'amber',
  publishedTemplates: 'green',
  completedTransactions: 'green',
  activeTenants: 'green',
  activeUsers: 'green',
};

function roleDescriptionKey(profile: ReturnType<typeof resolveDashboardProfile>): string {
  if (profile === 'platform_admin') {
    return 'dashboard.roleDescription.platform_admin';
  }
  if (profile === 'dept_chuyenvien' || profile === 'dept_lanhdao') {
    return 'adminUsers.systemRoleDesc.dept_user';
  }
  if (profile === 'dept_unassigned') {
    return 'dashboard.deptUnassigned';
  }
  return `adminUsers.systemRoleDesc.${profile}`;
}

export function DashboardPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user, tenant } = useAuth();
  const profile = user ? resolveDashboardProfile(user) : null;
  const { stats, quickLinks, isLoading, error } = useDashboardStats(user);

  const primaryDept = user?.departments?.[0];
  const roleLabel = profile
    ? t(`adminUsers.systemRole.${user?.system_role ?? 'dept_user'}`)
    : '';

  return (
    <>
      <PageHeader
        title={t('dashboard.title')}
        breadcrumb={[{ title: t('dashboard.title') }]}
      />

      <section className={styles.hero}>
        <div className={styles.heroContent}>
          <div className={styles.heroTags}>
            <Tag className={styles.roleTag}>{roleLabel}</Tag>
            {primaryDept ? (
              <Tag className={styles.deptTag}>
                {primaryDept.department_code} ·{' '}
                {t(`adminUsers.deptRole.${primaryDept.role}`)}
              </Tag>
            ) : null}
          </div>
          <Typography.Title level={2} className={styles.heroTitle}>
            {t('dashboard.welcome', { name: user?.display_name ?? '' })}
          </Typography.Title>
          <Typography.Paragraph className={styles.heroDesc}>
            {t('dashboard.description', { tenant: tenant?.name ?? '' })}
          </Typography.Paragraph>
          {profile && profile !== 'dept_unassigned' ? (
            <Typography.Paragraph className={styles.heroHint}>
              {t(roleDescriptionKey(profile))}
            </Typography.Paragraph>
          ) : null}
        </div>
      </section>

      {error ? (
        <Alert
          type="warning"
          showIcon
          className={styles.alert}
          message={t('dashboard.loadError')}
        />
      ) : null}

      {profile === 'dept_unassigned' ? (
        <Alert type="info" showIcon message={t('dashboard.deptUnassigned')} />
      ) : null}

      {profile !== 'dept_unassigned' ? (
        <Row gutter={[16, 16]} className={styles.statsRow}>
          {isLoading
            ? [0, 1, 2].map((i) => (
                <Col key={i} xs={24} sm={8}>
                  <div className={styles.skeletonCard}>
                    <LoadingSkeleton variant="text" rows={2} />
                  </div>
                </Col>
              ))
            : stats.map((stat) => (
                <Col
                  key={stat.key}
                  xs={24}
                  sm={stats.length <= 2 ? 12 : 8}
                >
                  <StatCard
                    title={t(stat.titleKey)}
                    value={stat.value}
                    icon={STAT_ICONS[stat.key] ?? <FileTextOutlined />}
                    accent={STAT_ACCENTS[stat.key] ?? 'blue'}
                    onClick={stat.link ? () => navigate(stat.link!) : undefined}
                  />
                </Col>
              ))}
        </Row>
      ) : null}

      {quickLinks.length > 0 ? (
        <section className={styles.quickLinks}>
          <h2 className={styles.quickLinksTitle}>{t('dashboard.quickLinks')}</h2>
          <div className={styles.quickLinksGrid}>
            {quickLinks.map((link) => (
              <button
                key={link.key}
                type="button"
                className={styles.quickLinkCard}
                onClick={() => navigate(link.path)}
              >
                <span>{t(link.labelKey)}</span>
                <ArrowRightOutlined aria-hidden />
              </button>
            ))}
          </div>
        </section>
      ) : null}

      {import.meta.env.VITE_BUILD_ID ? (
        <Typography.Text type="secondary" className={styles.buildInfo}>
          {t('dashboard.build', { id: import.meta.env.VITE_BUILD_ID })}
        </Typography.Text>
      ) : null}
    </>
  );
}
