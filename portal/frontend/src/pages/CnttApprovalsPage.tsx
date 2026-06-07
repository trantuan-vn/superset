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
  Form,
  Input,
  Modal,
  Space,
  Table,
  Typography,
  Upload,
  message,
} from 'antd';
import type { TableColumnsType } from 'antd';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { fetchTenantSettings } from '@/api/tenants';
import {
  ApiError,
  approveTemplate,
  fetchTemplateStepUpChallenge,
  fetchTemplates,
  previewTemplate,
  rejectTemplate,
  type ExportTemplate,
  type TemplatePreviewResult,
} from '@/api/templates';
import { LoadingSkeleton } from '@/components/LoadingSkeleton';
import { PageHeader } from '@/components/PageHeader';
import { StatusBadge } from '@/components/StatusBadge';
import { readFileAsText, signChallengeWithPrivateKey } from '@/features/auth/pkiSign';

import { useAuth } from '@/features/auth/useAuth';

const PENDING_KEY = ['templates', 'pending'] as const;

export function CnttApprovalsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { tenant } = useAuth();
  const [selected, setSelected] = useState<ExportTemplate | null>(null);
  const [preview, setPreview] = useState<TemplatePreviewResult | null>(null);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [pkiOpen, setPkiOpen] = useState(false);
  const [rejectForm] = Form.useForm<{ comment: string }>();
  const [pkiForm] = Form.useForm<{
    privateKeyFile: { originFileObj?: File }[];
    certificateFile: { originFileObj?: File }[];
  }>();

  const pendingQuery = useQuery({
    queryKey: PENDING_KEY,
    queryFn: () => fetchTemplates({ pending: true }),
  });

  const settingsQuery = useQuery({
    queryKey: ['tenant', 'settings', tenant?.id],
    queryFn: () => fetchTenantSettings(tenant?.id as string),
    enabled: Boolean(tenant?.id),
  });

  const pkiRequired =
    Boolean(settingsQuery.data?.digital_signature_enabled) &&
    Boolean(settingsQuery.data?.pki_config?.require_cert_at_approval);

  const rejectMutation = useMutation({
    mutationFn: ({ id, comment }: { id: string; comment: string }) =>
      rejectTemplate(id, comment),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PENDING_KEY });
      queryClient.invalidateQueries({ queryKey: ['templates'] });
      message.success(t('cnttApprovals.rejected'));
      setRejectOpen(false);
      setSelected(null);
      rejectForm.resetFields();
    },
    onError: (err) => {
      const text =
        err instanceof ApiError ? err.message : t('cnttApprovals.rejectFailed');
      message.error(text);
    },
  });

  const approveMutation = useMutation({
    mutationFn: (payload: { id: string; certificate?: string; signature?: string }) =>
      approveTemplate(payload.id, {
        certificate: payload.certificate,
        signature: payload.signature,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PENDING_KEY });
      queryClient.invalidateQueries({ queryKey: ['templates'] });
      message.success(t('cnttApprovals.approved'));
      setPkiOpen(false);
      setSelected(null);
      pkiForm.resetFields();
    },
    onError: (err) => {
      const text =
        err instanceof ApiError ? err.message : t('cnttApprovals.approveFailed');
      message.error(text);
    },
  });

  const previewMutation = useMutation({
    mutationFn: (template: ExportTemplate) => previewTemplate(template.id),
    onSuccess: (result) => setPreview(result),
    onError: (err) => {
      const text =
        err instanceof ApiError ? err.message : t('cnttApprovals.previewFailed');
      message.error(text);
    },
  });

  const openDrawer = (template: ExportTemplate) => {
    setSelected(template);
    setPreview(null);
    previewMutation.mutate(template);
  };

  const handleApproveClick = () => {
    if (!selected) {
      return;
    }
    if (pkiRequired) {
      setPkiOpen(true);
      return;
    }
    approveMutation.mutate({ id: selected.id });
  };

  const handlePkiApprove = async () => {
    if (!selected) {
      return;
    }
    const keyList = pkiForm.getFieldValue('privateKeyFile') as
      | { originFileObj?: File }[]
      | undefined;
    const certList = pkiForm.getFieldValue('certificateFile') as
      | { originFileObj?: File }[]
      | undefined;
    const keyFile = keyList?.[0]?.originFileObj;
    const certFile = certList?.[0]?.originFileObj;
    if (!keyFile || !certFile) {
      message.warning(t('cnttApprovals.pkiKeyRequired'));
      return;
    }
    try {
      const [certificate, privateKeyPem] = await Promise.all([
        readFileAsText(certFile),
        readFileAsText(keyFile),
      ]);
      const challenge = await fetchTemplateStepUpChallenge();
      const signature = await signChallengeWithPrivateKey(
        challenge.nonce,
        privateKeyPem,
      );
      await approveMutation.mutateAsync({
        id: selected.id,
        certificate,
        signature,
      });
    } catch (err) {
      const text =
        err instanceof Error ? err.message : t('cnttApprovals.approveFailed');
      message.error(text);
    }
  };

  const columns: TableColumnsType<ExportTemplate> = [
    {
      title: t('cnttApprovals.columns.name'),
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: t('cnttApprovals.columns.author'),
      dataIndex: 'created_by_name',
      key: 'created_by_name',
    },
    {
      title: t('cnttApprovals.columns.submitted'),
      dataIndex: 'submitted_at',
      key: 'submitted_at',
      render: (value: string | null) =>
        value ? new Date(value).toLocaleString() : '—',
    },
    {
      title: t('cnttApprovals.columns.status'),
      dataIndex: 'status',
      key: 'status',
      render: (status: ExportTemplate['status']) => <StatusBadge status={status} />,
    },
    {
      title: t('cnttApprovals.columns.actions'),
      key: 'actions',
      render: (_, record) => (
        <Button type="link" onClick={() => openDrawer(record)}>
          {t('cnttApprovals.view')}
        </Button>
      ),
    },
  ];

  const previewColumns =
    preview?.columns.map((column) => ({
      title: column,
      dataIndex: column,
      key: column,
      ellipsis: true,
    })) ?? [];

  return (
    <div>
      <PageHeader title={t('cnttApprovals.title')} />
      <Typography.Paragraph type="secondary">
        {t('cnttApprovals.subtitle')}
      </Typography.Paragraph>

      {pendingQuery.isLoading ? (
        <LoadingSkeleton variant="form" rows={4} />
      ) : (
        <Table
          rowKey="id"
          columns={columns}
          dataSource={pendingQuery.data ?? []}
          locale={{ emptyText: t('cnttApprovals.empty') }}
          pagination={{ pageSize: 10 }}
        />
      )}

      <Drawer
        title={selected?.name}
        open={Boolean(selected)}
        width={720}
        onClose={() => setSelected(null)}
        extra={
          selected ? (
            <Space>
              <Button danger onClick={() => setRejectOpen(true)}>
                {t('cnttApprovals.reject')}
              </Button>
              <Button
                type="primary"
                onClick={handleApproveClick}
                loading={approveMutation.isPending}
              >
                {t('cnttApprovals.approve')}
              </Button>
            </Space>
          ) : null
        }
      >
        {selected ? (
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <Space>
              <StatusBadge status={selected.status} />
              <Typography.Text type="secondary">
                {t('cnttApprovals.authorLabel', {
                  name: selected.created_by_name ?? selected.created_by,
                })}
              </Typography.Text>
            </Space>
            <div>
              <Typography.Text strong>{t('cnttApprovals.sqlLabel')}</Typography.Text>
              <Input.TextArea
                value={selected.sql_snapshot}
                readOnly
                rows={10}
                style={{ marginTop: 8, fontFamily: 'monospace' }}
              />
            </div>
            <div>
              <Typography.Text strong>{t('cnttApprovals.previewLabel')}</Typography.Text>
              {previewMutation.isPending ? (
                <LoadingSkeleton variant="form" rows={3} />
              ) : preview ? (
                <Table
                  size="small"
                  style={{ marginTop: 8 }}
                  columns={previewColumns}
                  dataSource={preview.rows.map((row, index) => ({
                    ...row,
                    key: String(index),
                  }))}
                  pagination={false}
                  scroll={{ x: true }}
                />
              ) : null}
            </div>
            {pkiRequired ? (
              <Alert
                type="info"
                showIcon
                message={t('cnttApprovals.pkiHintTitle')}
                description={t('cnttApprovals.pkiHintDesc')}
              />
            ) : null}
          </Space>
        ) : null}
      </Drawer>

      <Modal
        title={t('cnttApprovals.rejectTitle')}
        open={rejectOpen}
        onCancel={() => setRejectOpen(false)}
        onOk={() => rejectForm.submit()}
        confirmLoading={rejectMutation.isPending}
        okText={t('cnttApprovals.rejectConfirm')}
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
            label={t('cnttApprovals.rejectCommentLabel')}
            rules={[
              { required: true, message: t('cnttApprovals.rejectCommentRequired') },
              { whitespace: true, message: t('cnttApprovals.rejectCommentRequired') },
            ]}
          >
            <Input.TextArea rows={4} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={t('cnttApprovals.pkiTitle')}
        open={pkiOpen}
        onCancel={() => setPkiOpen(false)}
        onOk={handlePkiApprove}
        confirmLoading={approveMutation.isPending}
        okText={t('cnttApprovals.pkiConfirm')}
      >
        <Typography.Paragraph type="secondary">
          {t('cnttApprovals.pkiDesc')}
        </Typography.Paragraph>
        <Form form={pkiForm} layout="vertical">
          <Form.Item
            name="privateKeyFile"
            label={t('cnttApprovals.pkiKeyLabel')}
            valuePropName="fileList"
            getValueFromEvent={(event) => event.fileList}
          >
            <Upload beforeUpload={() => false} maxCount={1} accept=".key,.pem">
              <Button>{t('cnttApprovals.pkiKeyBrowse')}</Button>
            </Upload>
          </Form.Item>
          <Form.Item
            name="certificateFile"
            label={t('cnttApprovals.pkiCertLabel')}
            valuePropName="fileList"
            getValueFromEvent={(event) => event.fileList}
          >
            <Upload beforeUpload={() => false} maxCount={1} accept=".crt,.pem">
              <Button>{t('cnttApprovals.pkiCertBrowse')}</Button>
            </Upload>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
