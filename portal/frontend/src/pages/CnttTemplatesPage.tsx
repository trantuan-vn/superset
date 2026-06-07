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
import { useNavigate } from 'react-router-dom';
import { Button, Card, Empty, Space, Typography } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';

import { PageHeader } from '@/components/PageHeader';
import { useAuth } from '@/features/auth/useAuth';

export function CnttTemplatesPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { tenant } = useAuth();

  return (
    <div>
      <PageHeader
        title={t('cnttTemplates.title')}
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined aria-hidden />}
            onClick={() => navigate('/cntt/templates/new')}
          >
            {t('cnttTemplates.create')}
          </Button>
        }
      />
      <Typography.Paragraph type="secondary">
        {t('cnttTemplates.subtitle')}
      </Typography.Paragraph>

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
          <Button
            type="primary"
            onClick={() => navigate('/cntt/templates/new')}
          >
            {t('cnttTemplates.create')}
          </Button>
        </Empty>
      </Card>
    </div>
  );
}
