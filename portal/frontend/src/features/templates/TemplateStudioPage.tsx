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
import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Alert,
  Button,
  Card,
  Input,
  Modal,
  Space,
  Steps,
  Table,
  Typography,
  message,
} from 'antd';
import { useTranslation } from 'react-i18next';

import { ApiError } from '@/api/templates';
import {
  createTemplate,
  fetchTemplate,
  previewTemplate,
  submitTemplate,
  updateTemplate,
  type ExportTemplate,
  type TemplatePreviewResult,
} from '@/api/templates';
import { LoadingSkeleton } from '@/components/LoadingSkeleton';
import { PageHeader } from '@/components/PageHeader';
import { StatusBadge } from '@/components/StatusBadge';
import { AiAssistantPanel } from '@/features/templates/AiAssistantPanel';
import styles from '@/features/templates/TemplateStudioPage.module.css';
import { useAuth } from '@/features/auth/useAuth';

const DEFAULT_SQL =
  "SELECT *\nFROM portal_export_data\nWHERE tenant_id = '{{ current_user_tenant() }}'\nLIMIT 100";

function sqlDiffSummary(before: string, after: string): string {
  const beforeLines = before.trim().split('\n').length;
  const afterLines = after.trim().split('\n').length;
  return `${beforeLines} → ${afterLines}`;
}

function statusStepIndex(status: ExportTemplate['status']): number {
  switch (status) {
    case 'draft':
      return 0;
    case 'review':
      return 1;
    case 'published':
      return 2;
    default:
      return 0;
  }
}

export function TemplateStudioPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { id } = useParams<{ id: string }>();
  const { tenant, user } = useAuth();
  const isNew = id === 'new' || !id;

  const [name, setName] = useState('');
  const [sql, setSql] = useState(DEFAULT_SQL);
  const [pendingSql, setPendingSql] = useState<string | null>(null);
  const [showDiff, setShowDiff] = useState(false);
  const [preview, setPreview] = useState<TemplatePreviewResult | null>(null);

  const templateQuery = useQuery({
    queryKey: ['templates', id],
    queryFn: () => fetchTemplate(id as string),
    enabled: !isNew && Boolean(id),
  });

  const template = templateQuery.data;
  const aiEnabled = tenant?.ai_enabled ?? false;
  const isEditable = isNew || template?.status === 'draft';
  const isOwner = isNew || template?.created_by === user?.id;

  useEffect(() => {
    if (template) {
      setName(template.name);
      setSql(template.sql_snapshot || DEFAULT_SQL);
    }
  }, [template]);

  const breadcrumb = useMemo(
    () => [
      { title: t('nav.cnttTemplates'), href: '/cntt/templates' },
      {
        title: isNew
          ? t('templateStudio.newTitle')
          : template?.name ?? t('templateStudio.editTitle'),
      },
    ],
    [isNew, t, template?.name],
  );

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = { name: name.trim(), sql_snapshot: sql.trim() };
      if (isNew) {
        return createTemplate(payload);
      }
      return updateTemplate(id as string, payload);
    },
    onSuccess: (saved) => {
      queryClient.invalidateQueries({ queryKey: ['templates'] });
      message.success(t('templateStudio.saved'));
      if (isNew) {
        navigate(`/cntt/templates/${saved.id}`, { replace: true });
      }
    },
    onError: (err) => {
      const text =
        err instanceof ApiError ? err.message : t('templateStudio.saveFailed');
      message.error(text);
    },
  });

  const submitMutation = useMutation({
    mutationFn: () => submitTemplate(id as string),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['templates'] });
      queryClient.invalidateQueries({ queryKey: ['templates', id] });
      message.success(t('templateStudio.submitted'));
    },
    onError: (err) => {
      const text =
        err instanceof ApiError ? err.message : t('templateStudio.submitFailed');
      message.error(text);
    },
  });

  const previewMutation = useMutation({
    mutationFn: () => previewTemplate(id as string, sql.trim()),
    onSuccess: (result) => {
      setPreview(result);
    },
    onError: (err) => {
      const text =
        err instanceof ApiError ? err.message : t('templateStudio.previewFailed');
      message.error(text);
    },
  });

  const requestInsertSql = (nextSql: string) => {
    if (!sql.trim()) {
      setSql(nextSql);
      return;
    }
    if (sql.trim() === nextSql.trim()) {
      return;
    }
    setPendingSql(nextSql);
    setShowDiff(true);
  };

  const confirmInsert = () => {
    if (pendingSql) {
      setSql(pendingSql);
      setPendingSql(null);
    }
    setShowDiff(false);
  };

  const handleSaveDraft = async () => {
    if (!name.trim()) {
      message.warning(t('templateStudio.nameRequired'));
      return;
    }
    if (!sql.trim()) {
      message.warning(t('templateStudio.sqlRequired'));
      return;
    }
    await saveMutation.mutateAsync();
  };

  const handleSubmitReview = async () => {
    if (isNew) {
      message.warning(t('templateStudio.saveBeforeSubmit'));
      return;
    }
    if (!isOwner) {
      message.warning(t('templateStudio.ownerOnlySubmit'));
      return;
    }
    await submitMutation.mutateAsync();
  };

  const handlePreview = async () => {
    if (isNew) {
      message.warning(t('templateStudio.saveBeforePreview'));
      return;
    }
    await previewMutation.mutateAsync();
  };

  if (!isNew && templateQuery.isLoading) {
    return <LoadingSkeleton variant="form" rows={8} />;
  }

  if (!isNew && templateQuery.isError) {
    return (
      <Alert
        type="error"
        showIcon
        message={t('templateStudio.loadFailed')}
        action={
          <Button onClick={() => navigate('/cntt/templates')}>
            {t('templateStudio.backToList')}
          </Button>
        }
      />
    );
  }

  const previewColumns =
    preview?.columns.map((column) => ({
      title: column,
      dataIndex: column,
      key: column,
      ellipsis: true,
    })) ?? [];

  return (
    <div className={styles.studio}>
      <PageHeader
        title={
          isNew ? t('templateStudio.newTitle') : template?.name ?? t('templateStudio.editTitle')
        }
        breadcrumb={breadcrumb}
        extra={
          <Button onClick={() => navigate('/cntt/templates')}>
            {t('templateStudio.backToList')}
          </Button>
        }
      />

      {template?.reject_comment ? (
        <Alert
          type="warning"
          showIcon
          message={t('templateStudio.rejectTitle')}
          description={template.reject_comment}
        />
      ) : null}

      {!isNew && template ? (
        <Card size="small">
          <Steps
            size="small"
            current={statusStepIndex(template.status)}
            items={[
              { title: t('templateStudio.statusDraft') },
              { title: t('templateStudio.statusReview') },
              { title: t('templateStudio.statusPublished') },
            ]}
          />
        </Card>
      ) : null}

      <Card size="small">
        <Input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder={t('templateStudio.namePlaceholder')}
          disabled={!isEditable}
          aria-label={t('templateStudio.nameLabel')}
        />
      </Card>

      <div className={styles.split}>
        <Card className={styles.panel} title={t('templateStudio.aiPanel')}>
          <AiAssistantPanel
            aiEnabled={aiEnabled}
            contextSql={sql}
            onInsertSql={requestInsertSql}
          />
        </Card>

        <Card className={styles.panel} title={t('templateStudio.sqlPanel')}>
          <Input.TextArea
            className={styles.sqlEditor}
            value={sql}
            onChange={(event) => setSql(event.target.value)}
            rows={18}
            disabled={!isEditable}
            aria-label={t('templateStudio.sqlLabel')}
          />
        </Card>
      </div>

      <Card title={t('templateStudio.previewTitle')}>
        <Space style={{ marginBottom: 12 }}>
          <Button
            onClick={handlePreview}
            loading={previewMutation.isPending}
            disabled={isNew}
          >
            {t('templateStudio.runPreview')}
          </Button>
          {preview?.mock ? (
            <Typography.Text type="secondary">
              {t('templateStudio.previewMockHint')}
            </Typography.Text>
          ) : null}
        </Space>
        {preview ? (
          <Table
            size="small"
            columns={previewColumns}
            dataSource={preview.rows.map((row, index) => ({
              ...row,
              key: String(index),
            }))}
            pagination={false}
            scroll={{ x: true }}
          />
        ) : (
          <Typography.Text type="secondary">
            {t('templateStudio.previewEmpty')}
          </Typography.Text>
        )}
      </Card>

      <Card>
        <div className={styles.footer}>
          <Space>
            <Typography.Text type="secondary">
              {t('templateStudio.statusLabel')}
            </Typography.Text>
            <StatusBadge status={template?.status ?? 'draft'} />
          </Space>
          <Space>
            <Button
              onClick={handleSaveDraft}
              loading={saveMutation.isPending}
              disabled={!isEditable || !isOwner}
            >
              {t('templateStudio.saveDraft')}
            </Button>
            <Button
              type="primary"
              onClick={handleSubmitReview}
              loading={submitMutation.isPending}
              disabled={!isEditable || !isOwner || template?.status !== 'draft'}
            >
              {t('templateStudio.submitReview')}
            </Button>
          </Space>
        </div>
      </Card>

      <Modal
        title={t('templateStudio.diffTitle')}
        open={showDiff}
        onOk={confirmInsert}
        onCancel={() => {
          setPendingSql(null);
          setShowDiff(false);
        }}
        okText={t('templateStudio.diffConfirm')}
        cancelText={t('templateStudio.diffCancel')}
      >
        <Typography.Paragraph>
          {t('templateStudio.diffSummary', {
            summary: pendingSql ? sqlDiffSummary(sql, pendingSql) : '',
          })}
        </Typography.Paragraph>
        <Typography.Text strong>{t('templateStudio.diffBefore')}</Typography.Text>
        <Input.TextArea
          value={sql}
          readOnly
          rows={6}
          style={{ marginBottom: 12, fontFamily: 'monospace' }}
        />
        <Typography.Text strong>{t('templateStudio.diffAfter')}</Typography.Text>
        <Input.TextArea
          value={pendingSql ?? ''}
          readOnly
          rows={6}
          style={{ fontFamily: 'monospace' }}
        />
      </Modal>
    </div>
  );
}
