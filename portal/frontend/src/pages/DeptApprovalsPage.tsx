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
import { Alert, Button, Form, Input, Modal, Space, Table, Typography, message } from 'antd';
import type { TableColumnsType } from 'antd';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { fetchTemplateLaunchUrl } from '@/api/templates';
import {
  ApiError,
  approveTransaction,
  downloadTransaction,
  fetchPendingTransactions,
  rejectTransaction,
  type ExportTransaction,
} from '@/api/transactions';
import { LoadingSkeleton } from '@/components/LoadingSkeleton';
import { PageHeader } from '@/components/PageHeader';
import { openSupersetLaunch } from '@/components/ShareScopePicker';

const PENDING_KEY = ['dept', 'transactions', 'pending'] as const;

export function DeptApprovalsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [rejectOpen, setRejectOpen] = useState(false);
  const [selected, setSelected] = useState<ExportTransaction | null>(null);
  const [rejectForm] = Form.useForm<{ comment: string }>();

  const pendingQuery = useQuery({
    queryKey: PENDING_KEY,
    queryFn: fetchPendingTransactions,
  });

  const launchMutation = useMutation({
    mutationFn: (templateId: string) =>
      fetchTemplateLaunchUrl(templateId, 'dashboard_view'),
    onSuccess: ({ url }) => openSupersetLaunch(url),
    onError: (err) => {
      const text = err instanceof ApiError ? err.message : t('deptApprovals.launchFailed');
      message.error(text);
    },
  });

  const approveMutation = useMutation({
    mutationFn: approveTransaction,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PENDING_KEY });
      queryClient.invalidateQueries({ queryKey: ['dept', 'transactions'] });
      message.success(t('deptApprovals.approved'));
    },
    onError: (err) => {
      const text = err instanceof ApiError ? err.message : t('deptApprovals.approveFailed');
      message.error(text);
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, comment }: { id: string; comment: string }) =>
      rejectTransaction(id, comment),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PENDING_KEY });
      message.success(t('deptApprovals.rejected'));
      setRejectOpen(false);
      setSelected(null);
      rejectForm.resetFields();
    },
    onError: (err) => {
      const text = err instanceof ApiError ? err.message : t('deptApprovals.rejectFailed');
      message.error(text);
    },
  });

  const downloadMutation = useMutation({
    mutationFn: ({ id, format }: { id: string; format: 'csv' | 'pdf' }) =>
      downloadTransaction(id, format),
    onSuccess: () => message.success(t('deptApprovals.downloadStarted')),
    onError: (err) => {
      const text = err instanceof ApiError ? err.message : t('deptApprovals.downloadFailed');
      message.error(text);
    },
  });

  const columns: TableColumnsType<ExportTransaction> = [
    {
      title: t('deptApprovals.columns.template'),
      dataIndex: 'template_name',
      key: 'template_name',
    },
    {
      title: t('deptApprovals.columns.requester'),
      dataIndex: 'created_by_name',
      key: 'created_by_name',
    },
    {
      title: t('deptApprovals.columns.reason'),
      dataIndex: 'request_reason',
      key: 'request_reason',
      ellipsis: true,
      render: (value: string | null) =>
        value ? (
          <Typography.Text>{value}</Typography.Text>
        ) : (
          <Typography.Text type="secondary">—</Typography.Text>
        ),
    },
    {
      title: t('deptApprovals.columns.submitted'),
      dataIndex: 'submitted_at',
      key: 'submitted_at',
      render: (value: string | null) => (value ? new Date(value).toLocaleString() : '—'),
    },
    {
      title: t('deptApprovals.columns.actions'),
      key: 'actions',
      render: (_, record) => (
        <Space wrap>
          <Button
            size="small"
            onClick={() => launchMutation.mutate(record.template_id)}
            loading={launchMutation.isPending}
          >
            {t('deptApprovals.viewSuperset')}
          </Button>
          <Button
            type="primary"
            size="small"
            onClick={() => approveMutation.mutate(record.id)}
            loading={approveMutation.isPending}
          >
            {t('deptApprovals.approve')}
          </Button>
          <Button
            danger
            size="small"
            onClick={() => {
              setSelected(record);
              setRejectOpen(true);
            }}
          >
            {t('deptApprovals.reject')}
          </Button>
          <Button
            size="small"
            onClick={() =>
              approveMutation.mutateAsync(record.id).then(() =>
                downloadMutation.mutate({ id: record.id, format: 'csv' }),
              )
            }
            loading={approveMutation.isPending || downloadMutation.isPending}
          >
            {t('deptApprovals.approveDownloadCsv')}
          </Button>
          <Button
            size="small"
            onClick={() =>
              approveMutation.mutateAsync(record.id).then(() =>
                downloadMutation.mutate({ id: record.id, format: 'pdf' }),
              )
            }
            loading={approveMutation.isPending || downloadMutation.isPending}
          >
            {t('deptApprovals.approveDownloadPdf')}
          </Button>
        </Space>
      ),
    },
  ];

  if (pendingQuery.isLoading) {
    return <LoadingSkeleton variant="form" rows={4} />;
  }

  const pending = pendingQuery.data ?? [];
  const isEmpty = pending.length === 0;

  return (
    <div>
      <PageHeader
        title={t('deptApprovals.title')}
        subtitle={t('deptApprovals.subtitle')}
      />
      {isEmpty ? (
        <Alert
          type="info"
          showIcon
          message={t('deptApprovals.empty')}
          description={t('deptApprovals.emptyHint')}
          style={{ marginBottom: 16 }}
        />
      ) : null}
      <Table
        rowKey="id"
        columns={columns}
        dataSource={pending}
        locale={{ emptyText: t('deptApprovals.empty') }}
        pagination={{ pageSize: 10 }}
        scroll={{ x: true }}
      />

      <Modal
        title={t('deptApprovals.rejectTitle')}
        open={rejectOpen}
        onCancel={() => setRejectOpen(false)}
        onOk={() => rejectForm.submit()}
        confirmLoading={rejectMutation.isPending}
        okText={t('deptApprovals.rejectConfirm')}
      >
        <Form
          form={rejectForm}
          layout="vertical"
          onFinish={(values) => {
            if (!selected) {
              return;
            }
            rejectMutation.mutate({ id: selected.id, comment: values.comment });
          }}
        >
          <Form.Item
            name="comment"
            label={t('deptApprovals.rejectCommentLabel')}
            rules={[{ required: true, message: t('deptApprovals.rejectCommentRequired') }]}
          >
            <Input.TextArea rows={4} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
