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
  Card,
  Form,
  Input,
  Select,
  Space,
  Switch,
  Typography,
  message,
} from 'antd';
import { useTranslation } from 'react-i18next';

import { ApiError } from '@/api/auth';
import {
  fetchTenantSettings,
  updateTenantSettings,
  type TenantSettingsPatch,
} from '@/api/tenants';
import { PageHeader } from '@/components/PageHeader';
import { useAuth } from '@/features/auth/useAuth';

interface AuthSettingsFormValues {
  sso_ldap_enabled: boolean;
  auth_mode: 'local' | 'oidc' | 'saml' | 'ldap';
  ldap_uri?: string;
  bind_dn?: string;
  bind_password?: string;
  user_base_dn?: string;
  user_filter?: string;
  issuer_url?: string;
  client_id?: string;
  client_secret?: string;
  portal_password?: string;
}

const SETTINGS_KEY = ['tenant', 'settings'] as const;

export function AdminSettingsPage() {
  const { t } = useTranslation();
  const { tenant } = useAuth();
  const [form] = Form.useForm<AuthSettingsFormValues>();
  const queryClient = useQueryClient();

  const tenantId = tenant?.id ?? '';

  const { data, isLoading, error } = useQuery({
    queryKey: [...SETTINGS_KEY, tenantId],
    queryFn: () => fetchTenantSettings(tenantId),
    enabled: Boolean(tenantId),
  });

  const saveMutation = useMutation({
    mutationFn: (patch: TenantSettingsPatch) =>
      updateTenantSettings(tenantId, patch),
    onSuccess: () => {
      message.success(t('adminSettings.saved'));
      void queryClient.invalidateQueries({ queryKey: SETTINGS_KEY });
    },
    onError: (err: Error) => {
      const text =
        err instanceof ApiError ? err.message : t('adminSettings.saveError');
      message.error(text);
    },
  });

  if (!tenant) {
    return null;
  }

  const initialValues: AuthSettingsFormValues = {
    sso_ldap_enabled: data?.sso_ldap_enabled ?? false,
    auth_mode: data?.auth_mode ?? 'local',
    ldap_uri: (data?.sso_config?.ldap_uri as string) ?? '',
    bind_dn: (data?.sso_config?.bind_dn as string) ?? '',
    user_base_dn: (data?.sso_config?.user_base_dn as string) ?? '',
    user_filter: (data?.sso_config?.user_filter as string) ?? '(uid={username})',
    issuer_url: (data?.sso_config?.issuer_url as string) ?? '',
    client_id: (data?.sso_config?.client_id as string) ?? '',
  };

  const handleFinish = (values: AuthSettingsFormValues) => {
    const ssoConfig: Record<string, unknown> = {
      provider: values.auth_mode === 'ldap' ? 'ldap' : 'oidc',
    };

    if (values.auth_mode === 'ldap') {
      ssoConfig.ldap_uri = values.ldap_uri;
      ssoConfig.bind_dn = values.bind_dn;
      ssoConfig.user_base_dn = values.user_base_dn;
      ssoConfig.user_filter = values.user_filter;
      ssoConfig.bind_password_ref = 'secret/portal/ldap-bind';
      ssoConfig.attribute_mapping = {
        external_id: 'uid',
        email: 'mail',
        display_name: 'cn',
        dept_code: 'departmentNumber',
      };
      if (values.bind_password) {
        ssoConfig.bind_password = values.bind_password;
      }
    }

    if (values.auth_mode === 'oidc') {
      ssoConfig.issuer_url = values.issuer_url;
      ssoConfig.client_id = values.client_id;
      ssoConfig.client_secret_ref = 'secret/portal/keycloak-client';
      ssoConfig.scopes = ['openid', 'profile', 'email'];
      ssoConfig.attribute_mapping = {
        external_id: 'sub',
        email: 'email',
        display_name: 'name',
        dept_code: 'department',
      };
      if (values.client_secret) {
        ssoConfig.client_secret = values.client_secret;
      }
    }

    const patch: TenantSettingsPatch = {
      sso_ldap_enabled: values.sso_ldap_enabled,
      auth_mode: values.auth_mode,
      sso_config: values.sso_ldap_enabled ? ssoConfig : undefined,
    };
    if (values.sso_ldap_enabled && values.auth_mode === 'ldap') {
      patch.portal_password = values.portal_password?.trim() || undefined;
    }
    saveMutation.mutate(patch);
  };

  const authMode = Form.useWatch('auth_mode', form) ?? initialValues.auth_mode;
  const ssoEnabled =
    Form.useWatch('sso_ldap_enabled', form) ?? initialValues.sso_ldap_enabled;
  const ldapMigrationRequired =
    data?.ldap_migration_required ??
    (ssoEnabled && authMode === 'ldap' && !data?.sso_ldap_enabled);

  return (
    <div>
      <PageHeader title={t('adminSettings.title')} />
      <Typography.Paragraph type="secondary">
        {t('adminSettings.subtitle')}
      </Typography.Paragraph>

      {error ? (
        <Alert
          type="error"
          message={t('adminSettings.loadError')}
          showIcon
          style={{ marginBottom: 16 }}
        />
      ) : null}

      <Card loading={isLoading}>
        <Form<AuthSettingsFormValues>
          form={form}
          layout="vertical"
          initialValues={initialValues}
          key={data?.tenant_id ?? 'loading'}
          onFinish={handleFinish}
        >
          <Form.Item
            name="sso_ldap_enabled"
            label={t('adminSettings.ssoEnabled')}
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>

          <Form.Item name="auth_mode" label={t('adminSettings.authMode')}>
            <Select
              disabled={!ssoEnabled}
              options={[
                { value: 'local', label: t('adminSettings.modeLocal') },
                { value: 'ldap', label: t('adminSettings.modeLdap') },
                { value: 'oidc', label: t('adminSettings.modeOidc') },
                { value: 'saml', label: t('adminSettings.modeSaml'), disabled: true },
              ]}
            />
          </Form.Item>

          {ssoEnabled && authMode === 'ldap' ? (
            <>
              <Typography.Title level={5}>
                {t('adminSettings.ldapSection')}
              </Typography.Title>
              <Form.Item name="ldap_uri" label={t('adminSettings.ldapUri')}>
                <Input placeholder="ldap://localhost:1389" />
              </Form.Item>
              <Form.Item name="bind_dn" label={t('adminSettings.bindDn')}>
                <Input placeholder="cn=admin,dc=demo-corp,dc=local" />
              </Form.Item>
              <Form.Item
                name="bind_password"
                label={t('adminSettings.bindPassword')}
                extra={t('adminSettings.secretHint')}
              >
                <Input.Password placeholder="********" />
              </Form.Item>
              <Form.Item name="user_base_dn" label={t('adminSettings.userBaseDn')}>
                <Input placeholder="ou=people,dc=demo-corp,dc=local" />
              </Form.Item>
              <Form.Item name="user_filter" label={t('adminSettings.userFilter')}>
                <Input />
              </Form.Item>
              <Alert
                type="info"
                showIcon
                message={t('adminSettings.ldapMigrateTitle')}
                description={t('adminSettings.ldapMigrateHint')}
                style={{ marginBottom: 16 }}
              />
              <Form.Item
                name="portal_password"
                label={t('adminSettings.portalPassword')}
                rules={[
                  {
                    required: ldapMigrationRequired,
                    message: t('adminSettings.portalPasswordRequired'),
                  },
                ]}
                extra={t('adminSettings.portalPasswordHint')}
              >
                <Input.Password placeholder="Pass123!" />
              </Form.Item>
            </>
          ) : null}

          {ssoEnabled && authMode === 'oidc' ? (
            <>
              <Typography.Title level={5}>
                {t('adminSettings.oidcSection')}
              </Typography.Title>
              <Form.Item name="issuer_url" label={t('adminSettings.issuerUrl')}>
                <Input placeholder="http://localhost:8082/realms/demo-corp" />
              </Form.Item>
              <Form.Item name="client_id" label={t('adminSettings.clientId')}>
                <Input placeholder="portal" />
              </Form.Item>
              <Form.Item
                name="client_secret"
                label={t('adminSettings.clientSecret')}
                extra={t('adminSettings.secretHint')}
              >
                <Input.Password placeholder="********" />
              </Form.Item>
            </>
          ) : null}

          <Form.Item>
            <Space>
              <Button
                type="primary"
                htmlType="submit"
                loading={saveMutation.isPending}
              >
                {t('adminSettings.save')}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
