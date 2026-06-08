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
import { Tag } from 'antd';
import { useTranslation } from 'react-i18next';

import type { TemplateStatus } from '@/api/templates';
import type { TransactionStatus } from '@/api/transactions';

const TEMPLATE_COLORS: Record<TemplateStatus, string> = {
  draft: 'default',
  review: 'processing',
  published: 'success',
  archived: 'warning',
};

const TRANSACTION_COLORS: Record<TransactionStatus, string> = {
  draft: 'default',
  submitted: 'processing',
  approved: 'success',
  rejected: 'error',
  downloaded: 'cyan',
};

interface StatusBadgeProps {
  status: TemplateStatus | TransactionStatus;
  variant?: 'template' | 'transaction';
}

export function StatusBadge({ status, variant = 'template' }: StatusBadgeProps) {
  const { t } = useTranslation();
  if (variant === 'transaction') {
    const txnStatus = status as TransactionStatus;
    return (
      <Tag color={TRANSACTION_COLORS[txnStatus]}>
        {t(`statusBadge.transaction.${txnStatus}`)}
      </Tag>
    );
  }
  const templateStatus = status as TemplateStatus;
  return (
    <Tag color={TEMPLATE_COLORS[templateStatus]}>
      {t(`statusBadge.template.${templateStatus}`)}
    </Tag>
  );
}
