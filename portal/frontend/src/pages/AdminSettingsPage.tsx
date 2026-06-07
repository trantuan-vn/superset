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
import { useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Form,
  Input,
  Select,
  Space,
  Switch,
  Typography,
  Upload,
  message,
} from 'antd';
import type { UploadProps } from 'antd';
import { UploadOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';

import { ApiError } from '@/api/auth';
import {
  fetchTenantSettings,
  removeTenantCaCertificate,
  updateTenantSettings,
  uploadTenantCaCertificate,
  type TenantSettingsPatch,
} from '@/api/tenants';
import { PageHeader } from '@/components/PageHeader';
import { useAuth } from '@/features/auth/useAuth';

interface AuthSettingsFormValues {
  sso_ldap_enabled: boolean;
  auth_mode: 'local' | 'oidc' | 'saml' | 'ldap';
  digital_signature_enabled: boolean;
  ocsp_enabled: boolean;
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

  const caUploadMutation = useMutation({
    mutationFn: (certificate: string) =>
      uploadTenantCaCertificate(tenantId, certificate),
    onSuccess: () => {
      message.success(t('adminSettings.caUploaded'));
      void queryClient.invalidateQueries({ queryKey: SETTINGS_KEY });
    },
    onError: (err: Error) => {
      const text =
        err instanceof ApiError ? err.message : t('adminSettings.caUploadError');
      message.error(text);
    },
  });

  const caRemoveMutation = useMutation({
    mutationFn: () => removeTenantCaCertificate(tenantId),
    onSuccess: () => {
      message.success(t('adminSettings.caRemoved'));
      void queryClient.invalidateQueries({ queryKey: SETTINGS_KEY });
    },
    onError: (err: Error) => {
      const text =
        err instanceof ApiError ? err.message : t('adminSettings.caRemoveError');
      message.error(text);
    },
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
    digital_signature_enabled: data?.digital_signature_enabled ?? false,
    ocsp_enabled: Boolean(data?.pki_config?.ocsp_enabled),
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

    const pkiConfig: Record<string, unknown> = {
      ocsp_enabled: values.ocsp_enabled,
      require_cert_at_login: true,
      require_cert_at_approval: true,
      reject_expired: true,
      reject_revoked: true,
      allowed_eku: ['clientAuth', 'emailProtection'],
    };

    const patch: TenantSettingsPatch = {
      sso_ldap_enabled: values.sso_ldap_enabled,
      auth_mode: values.sso_ldap_enabled ? values.auth_mode : 'local',
      sso_config: values.sso_ldap_enabled ? ssoConfig : undefined,
      digital_signature_enabled: values.digital_signature_enabled,
      pki_config: values.digital_signature_enabled ? pkiConfig : undefined,
    };
    if (values.sso_ldap_enabled && values.auth_mode === 'ldap') {
      patch.portal_password = values.portal_password?.trim() || undefined;
    }
    saveMutation.mutate(patch);
  };

  const authMode = Form.useWatch('auth_mode', form) ?? initialValues.auth_mode;
  const ssoEnabled =
    Form.useWatch('sso_ldap_enabled', form) ?? initialValues.sso_ldap_enabled;

  useEffect(() => {
    if (!ssoEnabled && authMode !== 'local') {
      form.setFieldValue('auth_mode', 'local');
    }
  }, [authMode, form, ssoEnabled]);
  const pkiEnabled =
    Form.useWatch('digital_signature_enabled', form) ??
    initialValues.digital_signature_enabled;
  const ldapMigrationRequired =
    data?.ldap_migration_required ??
    (ssoEnabled && authMode === 'ldap' && !data?.sso_ldap_enabled);
  const caUploaded = Boolean(data?.pki_config?.ca_certificate_uploaded);
  const caSubjectDn = data?.pki_config?.ca_subject_dn as string | undefined;
  const caFingerprint = data?.pki_config?.ca_fingerprint as string | undefined;
  const caUploadedAt = data?.pki_config?.ca_uploaded_at as string | undefined;

  const caUploadProps: UploadProps = {
    accept: '.crt,.pem,.cer',
    showUploadList: false,
    beforeUpload: (file) => {
      const reader = new FileReader();
      reader.onload = () => {
        const text = reader.result;
        if (typeof text === 'string' && text.trim()) {
          caUploadMutation.mutate(text);
        }
      };
      reader.readAsText(file);
      return false;
    },
  };

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
            name="digital_signature_enabled"
            label={t('adminSettings.pkiEnabled')}
            valuePropName="checked"
            extra={t('adminSettings.pkiEnabledHint')}
          >
            <Switch />
          </Form.Item>

          {pkiEnabled ? (
            <Alert
              type="warning"
              showIcon
              message={t('adminSettings.pkiWarningTitle')}
              description={t('adminSettings.pkiWarningDesc')}
              style={{ marginBottom: 16 }}
            />
          ) : null}

          {pkiEnabled ? (
            <>
              <Typography.Title level={5}>
                {t('adminSettings.pkiSection')}
              </Typography.Title>
              <Typography.Paragraph type="secondary">
                {t('adminSettings.caUploadHint')}
              </Typography.Paragraph>
              {caUploaded ? (
                <Descriptions
                  bordered
                  size="small"
                  column={1}
                  style={{ marginBottom: 16 }}
                >
                  <Descriptions.Item label={t('adminSettings.caSubject')}>
                    {caSubjectDn ?? '—'}
                  </Descriptions.Item>
                  <Descriptions.Item label={t('adminSettings.caFingerprint')}>
                    <Typography.Text code>{caFingerprint ?? '—'}</Typography.Text>
                  </Descriptions.Item>
                  <Descriptions.Item label={t('adminSettings.caUploadedAt')}>
                    {caUploadedAt ?? '—'}
                  </Descriptions.Item>
                </Descriptions>
              ) : (
                <Alert
                  type="info"
                  showIcon
                  message={t('adminSettings.caMissingTitle')}
                  description={t('adminSettings.caMissingDesc')}
                  style={{ marginBottom: 16 }}
                />
              )}
              <Space style={{ marginBottom: 16 }}>
                <Upload {...caUploadProps}>
                  <Button
                    icon={<UploadOutlined />}
                    loading={caUploadMutation.isPending}
                  >
                    {caUploaded
                      ? t('adminSettings.caReplace')
                      : t('adminSettings.caUpload')}
                  </Button>
                </Upload>
                {caUploaded ? (
                  <Button
                    danger
                    loading={caRemoveMutation.isPending}
                    onClick={() => caRemoveMutation.mutate()}
                  >
                    {t('adminSettings.caRemove')}
                  </Button>
                ) : null}
              </Space>
              <Form.Item
                name="ocsp_enabled"
                label={t('adminSettings.ocspEnabled')}
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>
            </>
          ) : null}

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
