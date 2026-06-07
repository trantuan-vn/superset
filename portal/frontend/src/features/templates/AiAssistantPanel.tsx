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
import { useRef, useState } from 'react';
import { Alert, Button, Input, Space, Typography, message } from 'antd';
import { useTranslation } from 'react-i18next';

import { ApiError } from '@/api/auth';
import { streamGenerateSql } from '@/api/ai';
import { LoadingSkeleton } from '@/components/LoadingSkeleton';

interface AiAssistantPanelProps {
  aiEnabled: boolean;
  contextSql: string;
  onInsertSql: (sql: string) => void;
}

export function AiAssistantPanel({
  aiEnabled,
  contextSql,
  onInsertSql,
}: AiAssistantPanelProps) {
  const { t } = useTranslation();
  const [prompt, setPrompt] = useState('');
  const [draft, setDraft] = useState('');
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const handleGenerate = async () => {
    const trimmed = prompt.trim();
    if (!trimmed) {
      message.warning(t('templateStudio.ai.promptRequired'));
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setDraft('');
    try {
      await streamGenerateSql(
        {
          prompt: trimmed,
          context_sql: contextSql.trim() || undefined,
        },
        (event) => {
          if (event.type === 'chunk') {
            setDraft((prev) => prev + event.content);
          }
          if (event.type === 'error') {
            message.error(event.message);
          }
        },
        controller.signal,
      );
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        return;
      }
      const text =
        err instanceof ApiError ? err.message : t('templateStudio.ai.error');
      message.error(text);
    } finally {
      setLoading(false);
    }
  };

  const handleInsert = () => {
    if (!draft.trim()) {
      return;
    }
    onInsertSql(draft);
    message.success(t('templateStudio.ai.inserted'));
  };

  if (!aiEnabled) {
    return (
      <Alert
        type="info"
        showIcon
        message={t('templateStudio.ai.disabledTitle')}
        description={t('templateStudio.ai.disabledDesc')}
      />
    );
  }

  return (
    <div>
      <Typography.Title level={5}>{t('templateStudio.ai.title')}</Typography.Title>
      <Typography.Paragraph type="secondary">
        {t('templateStudio.ai.subtitle')}
      </Typography.Paragraph>
      <Input.TextArea
        value={prompt}
        onChange={(event) => setPrompt(event.target.value)}
        placeholder={t('templateStudio.ai.promptPlaceholder')}
        rows={4}
        disabled={loading}
        aria-label={t('templateStudio.ai.promptLabel')}
      />
      <Space style={{ marginTop: 12 }}>
        <Button type="primary" onClick={handleGenerate} loading={loading}>
          {t('templateStudio.ai.generate')}
        </Button>
        <Button
          onClick={handleInsert}
          disabled={!draft.trim() || loading}
        >
          {t('templateStudio.ai.insert')}
        </Button>
      </Space>
      {loading && !draft ? (
        <div style={{ marginTop: 16 }}>
          <LoadingSkeleton variant="form" rows={5} />
        </div>
      ) : null}
      {draft ? (
        <Input.TextArea
          value={draft}
          readOnly
          rows={10}
          style={{ marginTop: 16, fontFamily: 'monospace' }}
          aria-label={t('templateStudio.ai.draftLabel')}
        />
      ) : null}
    </div>
  );
}
