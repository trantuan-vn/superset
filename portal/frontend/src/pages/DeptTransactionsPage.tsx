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
import { Alert, Button, Space, Table, message } from 'antd';
import type { TableColumnsType } from 'antd';
import { useTranslation } from 'react-i18next';

import {
  ApiError,
  downloadTransaction,
  fetchMyTransactions,
  submitTransaction,
  type ExportTransaction,
} from '@/api/transactions';
import { LoadingSkeleton } from '@/components/LoadingSkeleton';
import { PageHeader } from '@/components/PageHeader';
import { StatusBadge } from '@/components/StatusBadge';

const TXN_KEY = ['dept', 'transactions'] as const;

export function DeptTransactionsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const txnsQuery = useQuery({
    queryKey: TXN_KEY,
    queryFn: fetchMyTransactions,
  });

  const submitMutation = useMutation({
    mutationFn: submitTransaction,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TXN_KEY });
      message.success(t('deptTransactions.submitted'));
    },
    onError: (err) => {
      const text = err instanceof ApiError ? err.message : t('deptTransactions.submitFailed');
      message.error(text);
    },
  });

  const downloadMutation = useMutation({
    mutationFn: ({ id, format }: { id: string; format: 'csv' | 'pdf' }) =>
      downloadTransaction(id, format),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: TXN_KEY });
      message.success(t('deptTransactions.downloadStarted'));
    },
    onError: (err) => {
      const text = err instanceof ApiError ? err.message : t('deptTransactions.downloadFailed');
      message.error(text);
    },
  });

  const columns: TableColumnsType<ExportTransaction> = [
    {
      title: t('deptTransactions.columns.template'),
      dataIndex: 'template_name',
      key: 'template_name',
    },
    {
      title: t('deptTransactions.columns.reason'),
      dataIndex: 'request_reason',
      key: 'request_reason',
      ellipsis: true,
      render: (value: string | null) => value ?? '—',
    },
    {
      title: t('deptTransactions.columns.status'),
      dataIndex: 'status',
      key: 'status',
      render: (status: ExportTransaction['status']) => (
        <StatusBadge status={status} variant="transaction" />
      ),
    },
    {
      title: t('deptTransactions.columns.submitted'),
      dataIndex: 'submitted_at',
      key: 'submitted_at',
      render: (value: string | null) => (value ? new Date(value).toLocaleString() : '—'),
    },
    {
      title: t('deptTransactions.columns.actions'),
      key: 'actions',
      render: (_, record) => (
        <Space>
          {record.status === 'draft' ? (
            <Button
              type="primary"
              size="small"
              onClick={() => submitMutation.mutate(record.id)}
              loading={submitMutation.isPending}
            >
              {t('deptTransactions.submit')}
            </Button>
          ) : null}
          {record.status === 'approved' || record.status === 'downloaded' ? (
            <>
              <Button
                size="small"
                onClick={() => downloadMutation.mutate({ id: record.id, format: 'csv' })}
                loading={downloadMutation.isPending}
              >
                {t('deptTransactions.downloadCsv')}
              </Button>
              <Button
                size="small"
                onClick={() => downloadMutation.mutate({ id: record.id, format: 'pdf' })}
                loading={downloadMutation.isPending}
              >
                {t('deptTransactions.downloadPdf')}
              </Button>
            </>
          ) : null}
        </Space>
      ),
    },
  ];

  if (txnsQuery.isLoading) {
    return <LoadingSkeleton variant="form" rows={4} />;
  }

  const hasDrafts = (txnsQuery.data ?? []).some((txn) => txn.status === 'draft');

  return (
    <div>
      <PageHeader
        title={t('deptTransactions.title')}
        subtitle={t('deptTransactions.subtitle')}
      />
      {hasDrafts ? (
        <Alert
          type="info"
          showIcon
          message={t('deptTransactions.draftHint')}
          style={{ marginBottom: 16 }}
        />
      ) : null}
      <Table
        rowKey="id"
        columns={columns}
        dataSource={txnsQuery.data ?? []}
        locale={{ emptyText: t('deptTransactions.empty') }}
        pagination={{ pageSize: 10 }}
      />
    </div>
  );
}
