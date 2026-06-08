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
import { Button, Card, Col, Form, Input, Modal, Row, Space, Tag, Typography, message } from 'antd';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import { fetchTemplateLaunchUrl } from '@/api/templates';
import {
  ApiError,
  createTransaction,
  fetchDeptTemplates,
} from '@/api/transactions';
import { LoadingSkeleton } from '@/components/LoadingSkeleton';
import { PageHeader } from '@/components/PageHeader';
import { openSupersetLaunch } from '@/components/ShareScopePicker';
import { useAuth } from '@/features/auth/useAuth';
import {
  isDeptLeader,
  permissionContextFromUser,
} from '@/features/auth/permissions';

export function DeptTemplatesPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const isLeader =
    user !== null &&
    isDeptLeader(permissionContextFromUser(user));
  const [exportOpen, setExportOpen] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null);
  const [exportForm] = Form.useForm<{ reason: string }>();

  const templatesQuery = useQuery({
    queryKey: ['dept', 'templates'],
    queryFn: fetchDeptTemplates,
  });

  const launchMutation = useMutation({
    mutationFn: (templateId: string) =>
      fetchTemplateLaunchUrl(templateId, 'dashboard_view'),
    onSuccess: ({ url }) => openSupersetLaunch(url),
    onError: (err) => {
      const text = err instanceof ApiError ? err.message : t('deptTemplates.launchFailed');
      message.error(text);
    },
  });

  const createTxnMutation = useMutation({
    mutationFn: ({ templateId, reason }: { templateId: string; reason: string }) =>
      createTransaction(templateId, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dept', 'transactions'] });
      message.success(t('deptTemplates.transactionCreated'));
      setExportOpen(false);
      setSelectedTemplateId(null);
      exportForm.resetFields();
      navigate('/dept/transactions');
    },
    onError: (err) => {
      const text =
        err instanceof ApiError ? err.message : t('deptTemplates.transactionFailed');
      message.error(text);
    },
  });

  if (templatesQuery.isLoading) {
    return <LoadingSkeleton variant="form" rows={4} />;
  }

  const templates = templatesQuery.data ?? [];

  return (
    <div>
      <PageHeader title={t('deptTemplates.title')} />
      <Typography.Paragraph type="secondary">
        {isLeader ? t('deptTemplates.subtitleLeader') : t('deptTemplates.subtitle')}
      </Typography.Paragraph>

      {templates.length === 0 ? (
        <Typography.Text type="secondary">{t('deptTemplates.empty')}</Typography.Text>
      ) : (
        <Row gutter={[16, 16]}>
          {templates.map((template) => (
            <Col key={template.id} xs={24} md={12} lg={8}>
              <Card title={template.name}>
                <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                  <Typography.Text type="secondary">
                    {template.superset_dashboard_title ?? template.name}
                  </Typography.Text>
                  {template.shared_departments && template.shared_departments.length > 0 ? (
                    <Space wrap>
                      {template.shared_departments.map((dept) => (
                        <Tag key={dept.id}>{dept.code}</Tag>
                      ))}
                    </Space>
                  ) : null}
                  <Space wrap>
                    <Button
                      onClick={() => launchMutation.mutate(template.id)}
                      loading={launchMutation.isPending}
                    >
                      {t('deptTemplates.viewSuperset')}
                    </Button>
                    {!isLeader ? (
                      <Button
                        type="primary"
                        onClick={() => {
                          setSelectedTemplateId(template.id);
                          setExportOpen(true);
                        }}
                      >
                        {t('deptTemplates.requestExport')}
                      </Button>
                    ) : null}
                  </Space>
                </Space>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      <Modal
        title={t('deptTemplates.exportModalTitle')}
        open={exportOpen}
        onCancel={() => {
          setExportOpen(false);
          setSelectedTemplateId(null);
          exportForm.resetFields();
        }}
        onOk={() => exportForm.submit()}
        confirmLoading={createTxnMutation.isPending}
        okText={t('deptTemplates.exportModalConfirm')}
      >
        <Typography.Paragraph type="secondary">
          {t('deptTemplates.exportModalHint')}
        </Typography.Paragraph>
        <Form
          form={exportForm}
          layout="vertical"
          onFinish={(values) => {
            if (!selectedTemplateId) {
              return;
            }
            createTxnMutation.mutate({
              templateId: selectedTemplateId,
              reason: values.reason,
            });
          }}
        >
          <Form.Item
            name="reason"
            label={t('deptTemplates.reasonLabel')}
            rules={[{ required: true, message: t('deptTemplates.reasonRequired') }]}
          >
            <Input.TextArea rows={4} placeholder={t('deptTemplates.reasonPlaceholder')} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
