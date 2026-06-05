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
import { ReloadOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { Alert, Button, Card, Descriptions, Skeleton, Tag } from 'antd';
import { useTranslation } from 'react-i18next';

import { fetchHealth } from '@/api/client';
import { PageHeader } from '@/components/PageHeader';

export function HealthUiPage() {
  const { t } = useTranslation();

  const { data, error, isLoading, isFetching, refetch } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    retry: 1,
  });

  const statusColor =
    data?.status === 'ok'
      ? 'success'
      : data?.status === 'degraded'
        ? 'warning'
        : 'default';

  return (
    <>
      <PageHeader
        title={t('health.title')}
        breadcrumb={[
          { title: t('home.title'), href: '/' },
          { title: t('health.title') },
        ]}
        extra={
          <Button
            icon={<ReloadOutlined />}
            onClick={() => void refetch()}
            loading={isFetching}
            aria-label={t('health.retry')}
          >
            {t('health.retry')}
          </Button>
        }
      />

      {error && (
        <Alert
          type="error"
          message={t('health.error')}
          showIcon
          style={{ marginBottom: 16 }}
          role="alert"
        />
      )}

      <Card>
        {isLoading ? (
          <Skeleton active paragraph={{ rows: 4 }} aria-busy="true" />
        ) : data ? (
          <Descriptions bordered column={1} size="middle">
            <Descriptions.Item label={t('health.apiStatus')}>
              <Tag color={statusColor}>{data.status}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label={t('health.database')}>
              <Tag color={data.database === 'connected' ? 'success' : 'error'}>
                {data.database}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="App">{data.app}</Descriptions.Item>
            <Descriptions.Item label={t('health.environment')}>
              {data.env}
            </Descriptions.Item>
          </Descriptions>
        ) : (
          <Alert type="warning" message={t('health.error')} showIcon />
        )}
      </Card>
    </>
  );
}
