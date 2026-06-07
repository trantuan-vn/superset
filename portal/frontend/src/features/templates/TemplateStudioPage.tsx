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
import { useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Alert,
  Button,
  Card,
  Input,
  Modal,
  Space,
  Tag,
  Typography,
  message,
} from 'antd';
import { useTranslation } from 'react-i18next';

import { PageHeader } from '@/components/PageHeader';
import { AiAssistantPanel } from '@/features/templates/AiAssistantPanel';
import styles from '@/features/templates/TemplateStudioPage.module.css';
import { useAuth } from '@/features/auth/useAuth';

function sqlDiffSummary(before: string, after: string): string {
  const beforeLines = before.trim().split('\n').length;
  const afterLines = after.trim().split('\n').length;
  return `${beforeLines} → ${afterLines}`;
}

export function TemplateStudioPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const { tenant } = useAuth();
  const [sql, setSql] = useState(
    'SELECT *\nFROM portal_export_data\nWHERE tenant_id = \'{{ current_user_tenant() }}\'\nLIMIT 100',
  );
  const [pendingSql, setPendingSql] = useState<string | null>(null);
  const [showDiff, setShowDiff] = useState(false);

  const aiEnabled = tenant?.ai_enabled ?? false;
  const isNew = id === 'new' || !id;

  const breadcrumb = useMemo(
    () => [
      { title: t('nav.cnttTemplates'), href: '/cntt/templates' },
      {
        title: isNew
          ? t('templateStudio.newTitle')
          : t('templateStudio.editTitle'),
      },
    ],
    [isNew, t],
  );

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

  const handleSaveDraft = () => {
    if (!sql.trim()) {
      message.warning(t('templateStudio.sqlRequired'));
      return;
    }
    message.success(t('templateStudio.draftSavedLocal'));
  };

  return (
    <div className={styles.studio}>
      <PageHeader
        title={
          isNew ? t('templateStudio.newTitle') : t('templateStudio.editTitle')
        }
        breadcrumb={breadcrumb}
        extra={
          <Button onClick={() => navigate('/cntt/templates')}>
            {t('templateStudio.backToList')}
          </Button>
        }
      />

      <Alert
        type="info"
        showIcon
        message={t('templateStudio.phase7HintTitle')}
        description={t('templateStudio.phase7HintDesc')}
      />

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
            aria-label={t('templateStudio.sqlLabel')}
          />
        </Card>
      </div>

      <Card>
        <div className={styles.footer}>
          <Space>
            <Typography.Text type="secondary">
              {t('templateStudio.statusLabel')}
            </Typography.Text>
            <Tag color="default">{t('templateStudio.statusDraft')}</Tag>
          </Space>
          <Space>
            <Button onClick={handleSaveDraft}>{t('templateStudio.saveDraft')}</Button>
            <Button type="primary" disabled>
              {t('templateStudio.submitReview')}
            </Button>
          </Space>
        </div>
        <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
          {t('templateStudio.previewComingPhase8')}
        </Typography.Paragraph>
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
