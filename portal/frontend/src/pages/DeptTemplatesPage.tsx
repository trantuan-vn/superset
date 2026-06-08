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
import { Button, Col, Form, Input, Modal, Row, Tag, message } from 'antd';
import { FileTextOutlined } from '@ant-design/icons';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import { fetchTemplateLaunchUrl } from '@/api/templates';
import {
  ApiError,
  createTransaction,
  fetchDeptTemplates,
} from '@/api/transactions';
import { ContentPanel } from '@/components/ContentPanel';
import { EmptyState } from '@/components/EmptyState';
import { LoadingSkeleton } from '@/components/LoadingSkeleton';
import { PageHeader } from '@/components/PageHeader';
import { openSupersetLaunch } from '@/components/ShareScopePicker';
import { useAuth } from '@/features/auth/useAuth';
import {
  isDeptLeader,
  permissionContextFromUser,
} from '@/features/auth/permissions';

import styles from '@/components/TemplateCard.module.css';

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
    return (
      <>
        <PageHeader
          title={t('deptTemplates.title')}
          subtitle={
            isLeader ? t('deptTemplates.subtitleLeader') : t('deptTemplates.subtitle')
          }
        />
        <ContentPanel>
          <LoadingSkeleton variant="form" rows={4} />
        </ContentPanel>
      </>
    );
  }

  const templates = templatesQuery.data ?? [];

  return (
    <>
      <PageHeader
        title={t('deptTemplates.title')}
        subtitle={
          isLeader ? t('deptTemplates.subtitleLeader') : t('deptTemplates.subtitle')
        }
      />

      {templates.length === 0 ? (
        <ContentPanel>
          <EmptyState
            title={t('deptTemplates.empty')}
            icon={<FileTextOutlined />}
          />
        </ContentPanel>
      ) : (
        <Row gutter={[16, 16]}>
          {templates.map((template) => (
            <Col key={template.id} xs={24} md={12} lg={8}>
              <article className={styles.card}>
                <div className={styles.header}>
                  <span className={styles.iconWrap} aria-hidden>
                    <FileTextOutlined />
                  </span>
                  <div className={styles.titleBlock}>
                    <h3 className={styles.title}>{template.name}</h3>
                    <p className={styles.subtitle}>
                      {template.superset_dashboard_title ?? template.name}
                    </p>
                  </div>
                </div>
                {template.shared_departments && template.shared_departments.length > 0 ? (
                  <div className={styles.tags}>
                    {template.shared_departments.map((dept) => (
                      <Tag key={dept.id} className={styles.tag}>
                        {dept.code}
                      </Tag>
                    ))}
                  </div>
                ) : null}
                <div className={styles.actions}>
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
                </div>
              </article>
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
        <p style={{ color: 'var(--portal-text-secondary)', marginBottom: 16 }}>
          {t('deptTemplates.exportModalHint')}
        </p>
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
    </>
  );
}
