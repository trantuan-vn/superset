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
} from '@ant-design/icons';
import { Card, Col, Row, Statistic, Tag, Typography } from 'antd';
import { useTranslation } from 'react-i18next';

import { PageHeader } from '@/components/PageHeader';
import { useAuth } from '@/features/auth/useAuth';

export function DashboardPage() {
  const { t } = useTranslation();
  const { user, tenant } = useAuth();

  return (
    <>
      <PageHeader
        title={t('dashboard.title')}
        breadcrumb={[{ title: t('dashboard.title') }]}
      />

      <Card style={{ marginBottom: 24 }}>
        <Tag color="blue">{t('dashboard.phase')}</Tag>
        <Typography.Title level={3} style={{ marginTop: 16, marginBottom: 8 }}>
          {t('dashboard.welcome', { name: user?.display_name ?? '' })}
        </Typography.Title>
        <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
          {t('dashboard.description', { tenant: tenant?.name ?? '' })}
        </Typography.Paragraph>
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title={t('dashboard.stats.pendingApprovals')}
              value={0}
              prefix={<ClockCircleOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title={t('dashboard.stats.templates')}
              value={0}
              prefix={<FileTextOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card>
            <Statistic
              title={t('dashboard.stats.completed')}
              value={0}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>
    </>
  );
}
