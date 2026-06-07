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
import { useQuery } from '@tanstack/react-query';
import { Button, Card, Empty, Space, Table, Typography } from 'antd';
import type { TableColumnsType } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { fetchTemplates, type ExportTemplate } from '@/api/templates';
import { LoadingSkeleton } from '@/components/LoadingSkeleton';
import { PageHeader } from '@/components/PageHeader';
import { StatusBadge } from '@/components/StatusBadge';
import { useAuth } from '@/features/auth/useAuth';

const TEMPLATES_KEY = ['templates'] as const;

export function CnttTemplatesPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { tenant, user } = useAuth();
  const isDesigner = user?.system_role === 'cntt_chuyenvien';

  const templatesQuery = useQuery({
    queryKey: TEMPLATES_KEY,
    queryFn: () => fetchTemplates(),
  });

  const columns: TableColumnsType<ExportTemplate> = [
    {
      title: t('cnttTemplates.columns.name'),
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: t('cnttTemplates.columns.status'),
      dataIndex: 'status',
      key: 'status',
      render: (status: ExportTemplate['status']) => <StatusBadge status={status} />,
    },
    {
      title: t('cnttTemplates.columns.updated'),
      dataIndex: 'updated_at',
      key: 'updated_at',
      render: (value: string) => new Date(value).toLocaleString(),
    },
    {
      title: t('cnttTemplates.columns.actions'),
      key: 'actions',
      render: (_, record) => (
        <Button type="link" onClick={() => navigate(`/cntt/templates/${record.id}`)}>
          {t('cnttTemplates.view')}
        </Button>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title={t('cnttTemplates.title')}
        extra={
          isDesigner ? (
            <Button
              type="primary"
              icon={<PlusOutlined aria-hidden />}
              onClick={() => navigate('/cntt/templates/new')}
            >
              {t('cnttTemplates.create')}
            </Button>
          ) : null
        }
      />
      <Typography.Paragraph type="secondary">
        {t('cnttTemplates.subtitle')}
      </Typography.Paragraph>

      {templatesQuery.isLoading ? (
        <LoadingSkeleton variant="form" rows={5} />
      ) : templatesQuery.isError ? (
        <Card>
          <Empty description={t('cnttTemplates.loadFailed')} />
        </Card>
      ) : templatesQuery.data && templatesQuery.data.length > 0 ? (
        <Card>
          <Table
            rowKey="id"
            columns={columns}
            dataSource={templatesQuery.data}
            pagination={{ pageSize: 10 }}
          />
        </Card>
      ) : (
        <Card>
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              <Space direction="vertical" size={4}>
                <Typography.Text>{t('cnttTemplates.emptyTitle')}</Typography.Text>
                <Typography.Text type="secondary">
                  {tenant?.ai_enabled
                    ? t('cnttTemplates.emptyAiOn')
                    : t('cnttTemplates.emptyAiOff')}
                </Typography.Text>
              </Space>
            }
          >
            {isDesigner ? (
              <Button
                type="primary"
                onClick={() => navigate('/cntt/templates/new')}
              >
                {t('cnttTemplates.create')}
              </Button>
            ) : null}
          </Empty>
        </Card>
      )}
    </div>
  );
}
