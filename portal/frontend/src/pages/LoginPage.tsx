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
import { EyeInvisibleOutlined, EyeTwoTone, LoginOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { Alert, Button, Checkbox, Divider, Form, Input, Typography } from 'antd';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom';

import { ApiError, fetchLoginOptions, ssoLoginUrl } from '@/api/auth';
import { BrandPanel } from '@/components/BrandPanel';
import { useAuth } from '@/features/auth/useAuth';

import styles from './LoginPage.module.css';

interface LoginFormValues {
  tenant_slug: string;
  username: string;
  password: string;
  remember: boolean;
}

export function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { login, logout, user, isAuthenticated, isLoading, pkiPending } = useAuth();
  const [form] = Form.useForm<LoginFormValues>();
  const [submitting, setSubmitting] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const tenantSlug = Form.useWatch('tenant_slug', form) ?? 'demo-corp';

  const { data: loginOptions } = useQuery({
    queryKey: ['auth', 'login-options', tenantSlug],
    queryFn: () => fetchLoginOptions(tenantSlug.trim()),
    enabled: tenantSlug.trim().length > 0,
    staleTime: 30_000,
  });

  useEffect(() => {
    const ssoError = searchParams.get('sso_error');
    if (ssoError) {
      setError(ssoError);
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    const tenantFromQuery = searchParams.get('tenant')?.trim();
    if (tenantFromQuery) {
      form.setFieldValue('tenant_slug', tenantFromQuery);
    }
  }, [form, searchParams]);

  const from =
    (location.state as { from?: string } | null)?.from ?? '/dashboard';

  const showSsoButton =
    loginOptions?.sso_enabled && loginOptions.auth_mode === 'oidc';
  const showLocalForm =
    loginOptions?.show_local_login !== false || !loginOptions?.sso_enabled;
  const ssoIsPrimary = loginOptions?.sso_primary === true;

  if (isAuthenticated) {
    return <Navigate to={from} replace />;
  }

  const handleSignOutPending = async () => {
    setSigningOut(true);
    try {
      await logout();
    } finally {
      setSigningOut(false);
    }
  };

  const renderFormCard = (children: React.ReactNode) => (
    <section className={styles.formPanel}>
      <div className={styles.formWrapper}>
        <div className={styles.formHeader}>
          <Typography.Title level={3} className={styles.formTitle}>
            {t('auth.loginTitle')}
          </Typography.Title>
          <Typography.Paragraph className={styles.formSubtitle}>
            {t('auth.loginSubtitle')}
          </Typography.Paragraph>
        </div>
        {children}
      </div>
    </section>
  );

  if (pkiPending && user) {
    return (
      <div className={styles.page}>
        <BrandPanel />
        {renderFormCard(
          <>
            <Alert
              type="info"
              showIcon
              message={t('pki.pendingSessionTitle')}
              description={t('pki.pendingSessionDesc', { name: user.display_name })}
              className={styles.errorAlert}
            />
            <Button
              type="primary"
              block
              size="large"
              onClick={() => navigate('/login/pki', { replace: true, state: { from } })}
            >
              {t('pki.continueVerify')}
            </Button>
            <Button
              block
              size="large"
              loading={signingOut}
              onClick={() => void handleSignOutPending()}
              className={styles.secondaryButton}
            >
              {t('pki.signOutAndLogin')}
            </Button>
          </>,
        )}
      </div>
    );
  }

  const handleSsoLogin = () => {
    const slug = form.getFieldValue('tenant_slug')?.trim() || 'demo-corp';
    window.location.href = ssoLoginUrl(slug);
  };

  const handleSubmit = async (values: LoginFormValues) => {
    setSubmitting(true);
    setError(null);
    try {
      const result = await login({
        tenant_slug: values.tenant_slug.trim().toLowerCase(),
        username: values.username.trim(),
        password: values.password,
      });
      if (result.pki_pending) {
        navigate('/login/pki', { replace: true, state: { from } });
      } else {
        navigate(from, { replace: true });
      }
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : t('auth.loginError');
      setError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={styles.page}>
      <BrandPanel />

      {renderFormCard(
        <>
          {error ? (
            <Alert
              type="error"
              message={error}
              showIcon
              className={styles.errorAlert}
              role="alert"
            />
          ) : null}

          <Form<LoginFormValues>
            form={form}
            layout="vertical"
            requiredMark={false}
            initialValues={{
              tenant_slug: 'demo-corp',
              remember: true,
            }}
            onFinish={handleSubmit}
            disabled={isLoading}
            className={styles.form}
          >
            <Form.Item
              name="tenant_slug"
              label={t('auth.tenantSlug')}
              rules={[{ required: true, message: t('auth.tenantRequired') }]}
            >
              <Input
                autoComplete="organization"
                aria-required
                placeholder="demo-corp"
                size="large"
              />
            </Form.Item>

            {showSsoButton ? (
              <Form.Item>
                <Button
                  type={ssoIsPrimary ? 'primary' : 'default'}
                  block
                  size="large"
                  icon={<LoginOutlined />}
                  onClick={handleSsoLogin}
                >
                  {t('auth.ssoButton')}
                </Button>
              </Form.Item>
            ) : null}

            {showSsoButton && showLocalForm ? (
              <Divider plain className={styles.divider}>
                {t('auth.orLocalLogin')}
              </Divider>
            ) : null}

            {showLocalForm ? (
              <>
                <Form.Item
                  name="username"
                  label={t('auth.username')}
                  rules={[
                    { required: true, message: t('auth.usernameRequired') },
                  ]}
                >
                  <Input
                    autoComplete="username"
                    aria-required
                    size="large"
                    placeholder={
                      loginOptions?.sso_enabled &&
                      loginOptions?.auth_mode === 'ldap'
                        ? 'cntt.cv'
                        : 'admin@demo-corp'
                    }
                  />
                </Form.Item>

                <Form.Item
                  name="password"
                  label={t('auth.password')}
                  rules={[
                    { required: true, message: t('auth.passwordRequired') },
                  ]}
                >
                  <Input.Password
                    autoComplete="current-password"
                    aria-required
                    size="large"
                    iconRender={(visible) =>
                      visible ? <EyeTwoTone /> : <EyeInvisibleOutlined />
                    }
                  />
                </Form.Item>

                <Form.Item name="remember" valuePropName="checked">
                  <Checkbox>{t('auth.rememberMe')}</Checkbox>
                </Form.Item>

                <Form.Item>
                  <Button
                    type={ssoIsPrimary ? 'default' : 'primary'}
                    htmlType="submit"
                    block
                    loading={submitting}
                    size="large"
                  >
                    {loginOptions?.sso_enabled &&
                    loginOptions?.auth_mode === 'ldap'
                      ? t('auth.ldapLoginButton')
                      : t('auth.loginButton')}
                  </Button>
                </Form.Item>
              </>
            ) : null}
          </Form>
        </>,
      )}
    </div>
  );
}
