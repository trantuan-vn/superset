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
import { Button, Form, Input, Modal, Popconfirm, Space, Table, message } from 'antd';
import type { TableColumnsType } from 'antd';
import { FileTextOutlined, PlusOutlined } from '@ant-design/icons';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import {
  ApiError,
  createTemplate,
  deleteTemplate,
  fetchTemplates,
  type ExportTemplate,
} from '@/api/templates';
import { ContentPanel } from '@/components/ContentPanel';
import { EmptyState } from '@/components/EmptyState';
import { LoadingSkeleton } from '@/components/LoadingSkeleton';
import { PageHeader } from '@/components/PageHeader';
import { StatusBadge } from '@/components/StatusBadge';
import { useAuth } from '@/features/auth/useAuth';

const TEMPLATES_KEY = ['templates'] as const;

const DEFAULT_SQL =
  "SELECT *\nFROM portal_export_data\nWHERE tenant_id = '{{ current_user_tenant() }}'\nLIMIT 100";

interface CreateTemplateFormValues {
  name: string;
  description?: string;
}

export function CnttTemplatesPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { tenant, user } = useAuth();
  const isDesigner = user?.system_role === 'cntt_chuyenvien';
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm] = Form.useForm<CreateTemplateFormValues>();

  const templatesQuery = useQuery({
    queryKey: TEMPLATES_KEY,
    queryFn: () => fetchTemplates(),
  });

  const createMutation = useMutation({
    mutationFn: (values: CreateTemplateFormValues) =>
      createTemplate({
        name: values.name.trim(),
        description: values.description?.trim() || undefined,
        sql_snapshot: DEFAULT_SQL,
      }),
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: TEMPLATES_KEY });
      message.success(t('cnttTemplates.createSuccess'));
      setCreateOpen(false);
      createForm.resetFields();
      navigate(`/cntt/templates/${saved.id}`);
    },
    onError: (err) => {
      const text =
        err instanceof ApiError ? err.message : t('cnttTemplates.createFailed');
      message.error(text);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteTemplate(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TEMPLATES_KEY });
      message.success(t('cnttTemplates.deleteSuccess'));
    },
    onError: (err) => {
      const text =
        err instanceof ApiError ? err.message : t('cnttTemplates.deleteFailed');
      message.error(text);
    },
  });

  const canManage = (record: ExportTemplate) =>
    isDesigner && record.created_by === user?.id && record.status === 'draft';

  const columns: TableColumnsType<ExportTemplate> = [
    {
      title: t('cnttTemplates.columns.name'),
      dataIndex: 'name',
      key: 'name',
      render: (name: string) => (
        <span style={{ fontWeight: 500, color: 'var(--portal-text)' }}>{name}</span>
      ),
    },
    {
      title: t('cnttTemplates.columns.status'),
      dataIndex: 'status',
      key: 'status',
      width: 140,
      render: (status: ExportTemplate['status']) => <StatusBadge status={status} />,
    },
    {
      title: t('cnttTemplates.columns.updated'),
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 200,
      render: (value: string) => (
        <span style={{ color: 'var(--portal-text-secondary)' }}>
          {new Date(value).toLocaleString()}
        </span>
      ),
    },
    {
      title: t('cnttTemplates.columns.actions'),
      key: 'actions',
      width: 200,
      render: (_, record) => (
        <Space size="small">
          <Button
            type="link"
            onClick={() => navigate(`/cntt/templates/${record.id}`)}
          >
            {canManage(record) ? t('cnttTemplates.edit') : t('cnttTemplates.view')}
          </Button>
          {canManage(record) ? (
            <Popconfirm
              title={t('cnttTemplates.deleteConfirmTitle')}
              description={t('cnttTemplates.deleteConfirmDesc', { name: record.name })}
              okText={t('cnttTemplates.deleteConfirm')}
              cancelText={t('common.cancel')}
              okButtonProps={{ danger: true, loading: deleteMutation.isPending }}
              onConfirm={() => deleteMutation.mutate(record.id)}
            >
              <Button type="link" danger>
                {t('cnttTemplates.delete')}
              </Button>
            </Popconfirm>
          ) : null}
        </Space>
      ),
    },
  ];

  const openCreateModal = () => {
    setCreateOpen(true);
  };

  return (
    <>
      <PageHeader
        title={t('cnttTemplates.title')}
        subtitle={t('cnttTemplates.subtitle')}
        extra={
          isDesigner ? (
            <Button
              type="primary"
              icon={<PlusOutlined aria-hidden />}
              onClick={openCreateModal}
            >
              {t('cnttTemplates.create')}
            </Button>
          ) : null
        }
      />

      {templatesQuery.isLoading ? (
        <ContentPanel>
          <LoadingSkeleton variant="form" rows={5} />
        </ContentPanel>
      ) : templatesQuery.isError ? (
        <ContentPanel>
          <EmptyState
            title={t('cnttTemplates.loadFailed')}
            icon={<FileTextOutlined />}
          />
        </ContentPanel>
      ) : templatesQuery.data && templatesQuery.data.length > 0 ? (
        <ContentPanel noPadding>
          <Table
            rowKey="id"
            columns={columns}
            dataSource={templatesQuery.data}
            pagination={{ pageSize: 10, showSizeChanger: true }}
          />
        </ContentPanel>
      ) : (
        <ContentPanel>
          <EmptyState
            title={t('cnttTemplates.emptyTitle')}
            description={
              tenant?.ai_enabled
                ? t('cnttTemplates.emptyAiOn')
                : t('cnttTemplates.emptyAiOff')
            }
            icon={<FileTextOutlined />}
            action={
              isDesigner ? (
                <Button
                  type="primary"
                  icon={<PlusOutlined aria-hidden />}
                  onClick={openCreateModal}
                >
                  {t('cnttTemplates.create')}
                </Button>
              ) : undefined
            }
          />
        </ContentPanel>
      )}

      <Modal
        title={t('cnttTemplates.createModalTitle')}
        open={createOpen}
        onCancel={() => {
          setCreateOpen(false);
          createForm.resetFields();
        }}
        onOk={() => createForm.submit()}
        confirmLoading={createMutation.isPending}
        okText={t('cnttTemplates.createModalConfirm')}
        cancelText={t('common.cancel')}
        destroyOnClose
      >
        <p style={{ color: 'var(--portal-text-secondary)', marginBottom: 16 }}>
          {t('cnttTemplates.createModalHint')}
        </p>
        <Form
          form={createForm}
          layout="vertical"
          onFinish={(values) => createMutation.mutate(values)}
        >
          <Form.Item
            name="name"
            label={t('cnttTemplates.createNameLabel')}
            rules={[{ required: true, message: t('cnttTemplates.createNameRequired') }]}
          >
            <Input placeholder={t('cnttTemplates.createNamePlaceholder')} />
          </Form.Item>
          <Form.Item name="description" label={t('cnttTemplates.createDescLabel')}>
            <Input.TextArea
              rows={3}
              placeholder={t('cnttTemplates.createDescPlaceholder')}
            />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
