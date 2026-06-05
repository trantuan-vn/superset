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
import { Card, Tag, Typography } from 'antd';
import { useTranslation } from 'react-i18next';

import { PageHeader } from '@/components/PageHeader';

export function HomePage() {
  const { t } = useTranslation();

  return (
    <>
      <PageHeader
        title={t('home.title')}
        breadcrumb={[{ title: t('home.title') }]}
      />
      <Card>
        <Tag color="blue">{t('home.phase')}</Tag>
        <Typography.Title level={3} style={{ marginTop: 16 }}>
          {t('home.welcome')}
        </Typography.Title>
        <Typography.Paragraph type="secondary">
          {t('home.description')}
        </Typography.Paragraph>
        <Typography.Paragraph>
          <Typography.Text strong>{t('app.tagline')}</Typography.Text>
        </Typography.Paragraph>
      </Card>
    </>
  );
}
