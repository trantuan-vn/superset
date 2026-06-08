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
  CheckCircleOutlined,
  ClockCircleOutlined,
  FileTextOutlined,
  SwapOutlined,
  TeamOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { Alert, Button, Card, Col, Row, Space, Statistic, Tag, Typography } from 'antd';
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import { LoadingSkeleton } from '@/components/LoadingSkeleton';
import { PageHeader } from '@/components/PageHeader';
import {
  resolveDashboardProfile,
  useDashboardStats,
} from '@/features/dashboard/useDashboardStats';
import { useAuth } from '@/features/auth/useAuth';

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

      <Card style={{ marginBottom: 24 }}>
        <Space wrap size={[8, 8]} style={{ marginBottom: 12 }}>
          <Tag color="blue">{roleLabel}</Tag>
          {primaryDept ? (
            <Tag>
              {primaryDept.department_code} ·{' '}
              {t(`adminUsers.deptRole.${primaryDept.role}`)}
            </Tag>
          ) : null}
        </Space>
        <Typography.Title level={3} style={{ marginTop: 0, marginBottom: 8 }}>
          {t('dashboard.welcome', { name: user?.display_name ?? '' })}
        </Typography.Title>
        <Typography.Paragraph type="secondary" style={{ marginBottom: 8 }}>
          {t('dashboard.description', { tenant: tenant?.name ?? '' })}
        </Typography.Paragraph>
        {profile && profile !== 'dept_unassigned' ? (
          <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
            {t(roleDescriptionKey(profile))}
          </Typography.Paragraph>
        ) : null}
      </Card>

      {error ? (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 24 }}
          message={t('dashboard.loadError')}
        />
      ) : null}

      {profile === 'dept_unassigned' ? (
        <Alert type="info" showIcon message={t('dashboard.deptUnassigned')} />
      ) : null}

      {profile !== 'dept_unassigned' ? (
        <Row gutter={[16, 16]} style={{ marginBottom: quickLinks.length ? 24 : 0 }}>
          {isLoading
            ? [0, 1, 2].map((i) => (
                <Col key={i} xs={24} sm={8}>
                  <Card>
                    <LoadingSkeleton variant="text" rows={2} />
                  </Card>
                </Col>
              ))
            : stats.map((stat) => (
                <Col
                  key={stat.key}
                  xs={24}
                  sm={stats.length <= 2 ? 12 : 8}
                >
                  <Card
                    hoverable={Boolean(stat.link)}
                    onClick={stat.link ? () => navigate(stat.link!) : undefined}
                    style={stat.link ? { cursor: 'pointer' } : undefined}
                  >
                    <Statistic
                      title={t(stat.titleKey)}
                      value={stat.value}
                      prefix={STAT_ICONS[stat.key] ?? <FileTextOutlined />}
                    />
                  </Card>
                </Col>
              ))}
        </Row>
      ) : null}

      {quickLinks.length > 0 ? (
        <Card title={t('dashboard.quickLinks')}>
          <Space wrap>
            {quickLinks.map((link) => (
              <Button key={link.key} type="link" onClick={() => navigate(link.path)}>
                {t(link.labelKey)}
              </Button>
            ))}
          </Space>
        </Card>
      ) : null}

      {import.meta.env.VITE_BUILD_ID ? (
        <Typography.Text
          type="secondary"
          style={{ display: 'block', marginTop: 24, fontSize: 12 }}
        >
          {t('dashboard.build', { id: import.meta.env.VITE_BUILD_ID })}
        </Typography.Text>
      ) : null}
    </>
  );
}
