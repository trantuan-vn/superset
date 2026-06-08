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
import { Radio, Select, Space, Typography } from 'antd';
import { useTranslation } from 'react-i18next';

import type { Department } from '@/api/departments';

export type ShareMode = 'ALL' | 'SELECTED';

export interface ShareScopePickerProps {
  mode: ShareMode;
  departmentIds: string[];
  departments: Department[];
  onModeChange: (mode: ShareMode) => void;
  onDepartmentIdsChange: (ids: string[]) => void;
}

export function ShareScopePicker({
  mode,
  departmentIds,
  departments,
  onModeChange,
  onDepartmentIdsChange,
}: ShareScopePickerProps) {
  const { t } = useTranslation();
  const selectedCount = mode === 'ALL' ? departments.length : departmentIds.length;

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Radio.Group
        value={mode}
        onChange={(event) => onModeChange(event.target.value as ShareMode)}
      >
        <Space direction="vertical">
          <Radio value="ALL">{t('shareScope.allDepartments')}</Radio>
          <Radio value="SELECTED">{t('shareScope.selectedDepartments')}</Radio>
        </Space>
      </Radio.Group>
      {mode === 'SELECTED' ? (
        <Select
          mode="multiple"
          allowClear
          showSearch
          optionFilterProp="label"
          placeholder={t('shareScope.selectPlaceholder')}
          value={departmentIds}
          onChange={onDepartmentIdsChange}
          options={departments.map((dept) => ({
            value: dept.id,
            label: `${dept.code} — ${dept.name}`,
          }))}
          style={{ width: '100%' }}
        />
      ) : null}
      <Typography.Text type="secondary">
        {t('shareScope.summary', { count: selectedCount })}
      </Typography.Text>
    </Space>
  );
}

export function openSupersetLaunch(url: string): void {
  window.open(url, '_blank', 'noopener,noreferrer');
}
