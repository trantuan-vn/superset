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
import { EyeInvisibleOutlined, EyeTwoTone } from '@ant-design/icons';
import { Alert, Button, Checkbox, Form, Input, Typography } from 'antd';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';

import { ApiError } from '@/api/auth';
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
  const { login, isAuthenticated, isLoading } = useAuth();
  const [form] = Form.useForm<LoginFormValues>();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const from =
    (location.state as { from?: string } | null)?.from ?? '/dashboard';

  if (isAuthenticated) {
    return <Navigate to={from} replace />;
  }

  const handleSubmit = async (values: LoginFormValues) => {
    setSubmitting(true);
    setError(null);
    try {
      await login({
        tenant_slug: values.tenant_slug.trim(),
        username: values.username.trim(),
        password: values.password,
      });
      navigate(from, { replace: true });
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
      <section className={styles.brandPanel} aria-hidden={false}>
        <div className={styles.brandContent}>
          <span className={styles.logoMark}>P</span>
          <Typography.Title level={2} className={styles.brandTitle}>
            {t('app.name')}
          </Typography.Title>
          <Typography.Paragraph className={styles.brandTagline}>
            {t('app.tagline')}
          </Typography.Paragraph>
        </div>
      </section>

      <section className={styles.formPanel}>
        <div className={styles.formWrapper}>
          <Typography.Title level={3}>{t('auth.loginTitle')}</Typography.Title>
          <Typography.Paragraph type="secondary">
            {t('auth.loginSubtitle')}
          </Typography.Paragraph>

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
              />
            </Form.Item>

            <Form.Item
              name="username"
              label={t('auth.username')}
              rules={[{ required: true, message: t('auth.usernameRequired') }]}
            >
              <Input
                autoComplete="username"
                aria-required
                placeholder="admin@demo-corp"
              />
            </Form.Item>

            <Form.Item
              name="password"
              label={t('auth.password')}
              rules={[{ required: true, message: t('auth.passwordRequired') }]}
            >
              <Input.Password
                autoComplete="current-password"
                aria-required
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
                type="primary"
                htmlType="submit"
                block
                loading={submitting}
                size="large"
              >
                {t('auth.loginButton')}
              </Button>
            </Form.Item>
          </Form>
        </div>
      </section>
    </div>
  );
}
