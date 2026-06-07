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
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Descriptions,
  Form,
  Input,
  Modal,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';

import { ApiError } from '@/api/auth';
import {
  createPlatformTenant,
  fetchPlatformTenants,
  type CreateTenantPayload,
  type PlatformTenant,
} from '@/api/platform';
import { PageHeader } from '@/components/PageHeader';

const TENANTS_KEY = ['platform', 'tenants'] as const;

interface CreateTenantFormValues {
  slug: string;
  name: string;
  admin_email: string;
  admin_password: string;
  admin_display_name: string;
}

interface CreatedTenantCredentials {
  slug: string;
  admin_email: string;
  admin_password: string;
}

export function PlatformTenantsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [successOpen, setSuccessOpen] = useState(false);
  const [createdCredentials, setCreatedCredentials] =
    useState<CreatedTenantCredentials | null>(null);
  const [form] = Form.useForm<CreateTenantFormValues>();

  const { data, isLoading, error } = useQuery({
    queryKey: TENANTS_KEY,
    queryFn: fetchPlatformTenants,
  });

  const createMutation = useMutation({
    mutationFn: (payload: CreateTenantPayload) => createPlatformTenant(payload),
    onSuccess: (_data, variables) => {
      setCreatedCredentials({
        slug: variables.slug,
        admin_email: variables.admin_email,
        admin_password: variables.admin_password,
      });
      setSuccessOpen(true);
      setModalOpen(false);
      form.resetFields();
      void queryClient.invalidateQueries({ queryKey: TENANTS_KEY });
    },
    onError: (err: Error) => {
      const text =
        err instanceof ApiError ? err.message : t('platformTenants.createError');
      message.error(text);
    },
  });

  const columns = [
    {
      title: t('platformTenants.slug'),
      dataIndex: 'slug',
      key: 'slug',
    },
    {
      title: t('platformTenants.name'),
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: t('platformTenants.admins'),
      dataIndex: 'admin_count',
      key: 'admin_count',
    },
    {
      title: t('platformTenants.pki'),
      key: 'pki_enabled',
      render: (_: unknown, row: PlatformTenant) =>
        row.pki_enabled ? (
          <Tag color="green">{t('platformTenants.pkiOn')}</Tag>
        ) : (
          <Tag>{t('platformTenants.pkiOff')}</Tag>
        ),
    },
    {
      title: t('platformTenants.status'),
      dataIndex: 'status',
      key: 'status',
    },
  ];

  const handleCreate = (values: CreateTenantFormValues) => {
    createMutation.mutate({
      slug: values.slug.trim().toLowerCase(),
      name: values.name.trim(),
      admin_email: values.admin_email.trim().toLowerCase(),
      admin_password: values.admin_password,
      admin_display_name: values.admin_display_name.trim(),
    });
  };

  return (
    <div>
      <PageHeader title={t('platformTenants.title')} />
      <Typography.Paragraph type="secondary">
        {t('platformTenants.subtitle')}
      </Typography.Paragraph>

      {error ? (
        <Alert
          type="error"
          message={t('platformTenants.loadError')}
          description={
            error instanceof ApiError ? error.message : error.message
          }
          showIcon
          style={{ marginBottom: 16 }}
        />
      ) : null}

      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" onClick={() => setModalOpen(true)}>
          {t('platformTenants.create')}
        </Button>
      </Space>

      <Table<PlatformTenant>
        rowKey="id"
        loading={isLoading}
        dataSource={data ?? []}
        columns={columns}
        pagination={false}
      />

      <Modal
        title={t('platformTenants.createTitle')}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        footer={null}
        destroyOnClose
      >
        <Form<CreateTenantFormValues>
          form={form}
          layout="vertical"
          onFinish={handleCreate}
        >
          <Form.Item
            name="slug"
            label={t('platformTenants.slug')}
            rules={[{ required: true, message: t('platformTenants.slugRequired') }]}
          >
            <Input placeholder="acme-corp" />
          </Form.Item>
          <Form.Item
            name="name"
            label={t('platformTenants.name')}
            rules={[{ required: true, message: t('platformTenants.nameRequired') }]}
          >
            <Input placeholder="ACME Corporation" />
          </Form.Item>
          <Typography.Title level={5}>
            {t('platformTenants.adminSection')}
          </Typography.Title>
          <Form.Item
            name="admin_display_name"
            label={t('platformTenants.adminName')}
            rules={[
              { required: true, message: t('platformTenants.adminNameRequired') },
            ]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="admin_email"
            label={t('platformTenants.adminEmail')}
            rules={[
              { required: true, message: t('platformTenants.adminEmailRequired') },
              { type: 'email', message: t('platformTenants.adminEmailInvalid') },
            ]}
          >
            <Input placeholder="admin@acme-corp" />
          </Form.Item>
          <Form.Item
            name="admin_password"
            label={t('platformTenants.adminPassword')}
            extra={t('platformTenants.adminPasswordHint')}
            rules={[
              { required: true, message: t('platformTenants.adminPasswordRequired') },
              { min: 8, message: t('platformTenants.adminPasswordMin') },
            ]}
          >
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button onClick={() => setModalOpen(false)}>
                {t('platformTenants.cancel')}
              </Button>
              <Button
                type="primary"
                htmlType="submit"
                loading={createMutation.isPending}
              >
                {t('platformTenants.submit')}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={t('platformTenants.successTitle')}
        open={successOpen}
        onCancel={() => setSuccessOpen(false)}
        footer={[
          <Button key="close" onClick={() => setSuccessOpen(false)}>
            {t('platformTenants.successClose')}
          </Button>,
          <Link
            key="login"
            to={`/login?tenant=${encodeURIComponent(createdCredentials?.slug ?? '')}`}
          >
            <Button type="primary">{t('platformTenants.goToLogin')}</Button>
          </Link>,
        ]}
      >
        <Typography.Paragraph>{t('platformTenants.successIntro')}</Typography.Paragraph>
        <Descriptions bordered column={1} size="small">
          <Descriptions.Item label={t('platformTenants.slug')}>
            {createdCredentials?.slug}
          </Descriptions.Item>
          <Descriptions.Item label={t('platformTenants.adminEmail')}>
            {createdCredentials?.admin_email}
          </Descriptions.Item>
          <Descriptions.Item label={t('platformTenants.adminPassword')}>
            <Typography.Text code copyable>
              {createdCredentials?.admin_password}
            </Typography.Text>
          </Descriptions.Item>
        </Descriptions>
        <Alert
          type="warning"
          showIcon
          message={t('platformTenants.successPasswordWarning')}
          style={{ marginTop: 16 }}
        />
      </Modal>
    </div>
  );
}
