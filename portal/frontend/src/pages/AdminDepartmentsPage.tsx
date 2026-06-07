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
  Drawer,
  Empty,
  Form,
  Input,
  Modal,
  Space,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import type { TableColumnsType } from 'antd';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ApiError } from '@/api/auth';
import {
  createDepartment,
  fetchDepartments,
  updateDepartment,
  type Department,
  type DepartmentStatus,
} from '@/api/departments';
import { PageHeader } from '@/components/PageHeader';
import { useAuth } from '@/features/auth/useAuth';

const DEPARTMENTS_KEY = ['admin', 'departments'] as const;

interface DepartmentFormValues {
  code: string;
  name: string;
}

export function AdminDepartmentsPage() {
  const { t } = useTranslation();
  const { isAuthenticated } = useAuth();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<Department | null>(null);
  const [deactivateTarget, setDeactivateTarget] = useState<Department | null>(null);
  const [form] = Form.useForm<DepartmentFormValues>();

  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: [...DEPARTMENTS_KEY, search],
    queryFn: () => fetchDepartments({ search: search || undefined }),
    enabled: isAuthenticated,
  });

  const createMutation = useMutation({
    mutationFn: createDepartment,
    onSuccess: () => {
      message.success(t('adminDepartments.created'));
      setDrawerOpen(false);
      form.resetFields();
      void queryClient.invalidateQueries({ queryKey: DEPARTMENTS_KEY });
    },
    onError: (err: Error) => {
      message.error(
        err instanceof ApiError ? err.message : t('adminDepartments.createError'),
      );
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: string;
      payload: { name?: string; status?: DepartmentStatus };
    }) => updateDepartment(id, payload),
    onSuccess: () => {
      message.success(t('adminDepartments.updated'));
      setDrawerOpen(false);
      setEditing(null);
      form.resetFields();
      void queryClient.invalidateQueries({ queryKey: DEPARTMENTS_KEY });
    },
    onError: (err: Error) => {
      message.error(
        err instanceof ApiError ? err.message : t('adminDepartments.updateError'),
      );
    },
  });

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    setDrawerOpen(true);
  };

  const openEdit = (dept: Department) => {
    setEditing(dept);
    form.setFieldsValue({ code: dept.code, name: dept.name });
    setDrawerOpen(true);
  };

  const handleSubmit = async () => {
    const values = await form.validateFields();
    if (editing) {
      updateMutation.mutate({
        id: editing.id,
        payload: { name: values.name },
      });
    } else {
      createMutation.mutate({
        code: values.code.toUpperCase(),
        name: values.name,
      });
    }
  };

  const confirmDeactivate = () => {
    if (!deactivateTarget) {
      return;
    }
    updateMutation.mutate(
      { id: deactivateTarget.id, payload: { status: 'inactive' } },
      {
        onSuccess: () => {
          setDeactivateTarget(null);
          message.success(t('adminDepartments.deactivated'));
        },
      },
    );
  };

  const columns: TableColumnsType<Department> = useMemo(
    () => [
      {
        title: t('adminDepartments.code'),
        dataIndex: 'code',
        sorter: (a, b) => a.code.localeCompare(b.code),
      },
      {
        title: t('adminDepartments.name'),
        dataIndex: 'name',
        sorter: (a, b) => a.name.localeCompare(b.name),
      },
      {
        title: t('adminDepartments.status'),
        dataIndex: 'status',
        render: (status: DepartmentStatus) => (
          <Tag color={status === 'active' ? 'green' : 'default'}>
            {status === 'active'
              ? t('adminDepartments.statusActive')
              : t('adminDepartments.statusInactive')}
          </Tag>
        ),
        filters: [
          { text: t('adminDepartments.statusActive'), value: 'active' },
          { text: t('adminDepartments.statusInactive'), value: 'inactive' },
        ],
        onFilter: (value, record) => record.status === value,
      },
      {
        title: t('adminDepartments.actions'),
        key: 'actions',
        render: (_, record) => (
          <Space>
            <Button type="link" size="small" onClick={() => openEdit(record)}>
              {t('adminDepartments.edit')}
            </Button>
            {record.status === 'active' ? (
              <Button
                type="link"
                size="small"
                danger
                onClick={() => setDeactivateTarget(record)}
              >
                {t('adminDepartments.deactivate')}
              </Button>
            ) : (
              <Button
                type="link"
                size="small"
                onClick={() =>
                  updateMutation.mutate({
                    id: record.id,
                    payload: { status: 'active' },
                  })
                }
              >
                {t('adminDepartments.reactivate')}
              </Button>
            )}
          </Space>
        ),
      },
    ],
    [t, updateMutation],
  );

  return (
    <>
      <PageHeader
        title={t('adminDepartments.title')}
        subtitle={t('adminDepartments.subtitle')}
        extra={
          <Button type="primary" onClick={openCreate}>
            {t('adminDepartments.create')}
          </Button>
        }
      />

      {error ? (
        <Alert
          type="error"
          showIcon
          message={t('adminDepartments.loadError')}
          description={
            error instanceof ApiError
              ? error.message
              : t('adminDepartments.loadErrorHint')
          }
          action={
            <Button
              size="small"
              loading={isFetching}
              onClick={() => {
                void refetch();
              }}
            >
              {t('adminDepartments.retry')}
            </Button>
          }
          style={{ marginBottom: 16 }}
        />
      ) : null}

      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Input.Search
          allowClear
          placeholder={t('adminDepartments.searchPlaceholder')}
          onSearch={setSearch}
          style={{ maxWidth: 360 }}
        />

        <Table<Department>
          rowKey="id"
          loading={isLoading}
          columns={columns}
          dataSource={data ?? []}
          locale={{
            emptyText: (
              <Empty
                description={t('adminDepartments.empty')}
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              />
            ),
          }}
        />
      </Space>

      <Drawer
        title={
          editing
            ? t('adminDepartments.editTitle')
            : t('adminDepartments.createTitle')
        }
        open={drawerOpen}
        onClose={() => {
          setDrawerOpen(false);
          setEditing(null);
        }}
        width={420}
        extra={
          <Space>
            <Button onClick={() => setDrawerOpen(false)}>
              {t('adminDepartments.cancel')}
            </Button>
            <Button
              type="primary"
              loading={createMutation.isPending || updateMutation.isPending}
              onClick={() => {
                void handleSubmit();
              }}
            >
              {t('adminDepartments.save')}
            </Button>
          </Space>
        }
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="code"
            label={t('adminDepartments.code')}
            rules={[
              { required: true, message: t('adminDepartments.codeRequired') },
              {
                pattern: /^[A-Z0-9_]{2,64}$/,
                message: t('adminDepartments.codeFormat'),
              },
            ]}
          >
            <Input
              disabled={Boolean(editing)}
              placeholder="KETOAN"
              onChange={(event) => {
                form.setFieldValue('code', event.target.value.toUpperCase());
              }}
            />
          </Form.Item>
          <Form.Item
            name="name"
            label={t('adminDepartments.name')}
            rules={[{ required: true, message: t('adminDepartments.nameRequired') }]}
          >
            <Input />
          </Form.Item>
          {!editing ? (
            <Typography.Paragraph type="secondary">
              {t('adminDepartments.codeHint')}
            </Typography.Paragraph>
          ) : null}
        </Form>
      </Drawer>

      <Modal
        title={t('adminDepartments.deactivateTitle')}
        open={Boolean(deactivateTarget)}
        onCancel={() => setDeactivateTarget(null)}
        onOk={confirmDeactivate}
        okText={t('adminDepartments.deactivateConfirm')}
        okButtonProps={{ danger: true, loading: updateMutation.isPending }}
      >
        <Typography.Paragraph>
          {t('adminDepartments.deactivateMessage', {
            name: deactivateTarget?.name,
            code: deactivateTarget?.code,
          })}
        </Typography.Paragraph>
      </Modal>
    </>
  );
}
