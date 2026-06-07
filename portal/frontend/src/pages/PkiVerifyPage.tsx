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
import { SafetyCertificateOutlined } from '@ant-design/icons';
import {
  Alert,
  Button,
  Modal,
  Steps,
  Typography,
  Upload,
  message,
} from 'antd';
import type { UploadFile } from 'antd/es/upload/interface';
import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';

import { ApiError, fetchPkiChallenge, verifyPki } from '@/api/auth';
import {
  readFileAsText,
  signChallengeWithPrivateKey,
} from '@/features/auth/pkiSign';
import { useAuth } from '@/features/auth/useAuth';

import styles from './PkiVerifyPage.module.css';

type PkiUiState =
  | 'waiting_token'
  | 'select_cert'
  | 'verifying'
  | 'success'
  | 'error';

export function PkiVerifyPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { user, isLoading, pkiPending, refresh, logout } = useAuth();
  const [uiState, setUiState] = useState<PkiUiState>('waiting_token');
  const [error, setError] = useState<string | null>(null);
  const [certFile, setCertFile] = useState<UploadFile[]>([]);
  const [keyFile, setKeyFile] = useState<UploadFile[]>([]);
  const [helpOpen, setHelpOpen] = useState(false);
  const [selectedCert, setSelectedCert] = useState<File | null>(null);
  const [selectedKey, setSelectedKey] = useState<File | null>(null);
  const [signingOut, setSigningOut] = useState(false);

  const from =
    (location.state as { from?: string } | null)?.from ?? '/dashboard';

  useEffect(() => {
    if (isLoading || !user) {
      return;
    }
    if (!pkiPending) {
      setUiState('success');
      return;
    }
    setUiState((prev) => (prev === 'waiting_token' ? 'select_cert' : prev));
  }, [isLoading, user, pkiPending]);

  const handleVerify = useCallback(async () => {
    const certOrigin = selectedCert ?? certFile[0]?.originFileObj;
    const keyOrigin = selectedKey ?? keyFile[0]?.originFileObj;
    if (!certOrigin || !keyOrigin) {
      const msg = t('pki.certKeyRequired');
      setError(msg);
      setUiState('error');
      message.error(msg);
      return;
    }

    setUiState('verifying');
    setError(null);

    try {
      const [certificate, privateKeyPem] = await Promise.all([
        readFileAsText(certOrigin),
        readFileAsText(keyOrigin),
      ]);
      const challenge = await fetchPkiChallenge();
      const signature = await signChallengeWithPrivateKey(
        challenge.nonce,
        privateKeyPem,
      );
      await verifyPki({ certificate, signature });
      await refresh();
      setUiState('success');
      message.success(t('pki.verifySuccess'));
      navigate(from, { replace: true });
    } catch (err) {
      const text =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : t('pki.verifyError');
      setError(text);
      setUiState('error');
      message.error(text);
    }
  }, [certFile, keyFile, from, navigate, refresh, selectedCert, selectedKey, t]);

  const handleSignOut = useCallback(async () => {
    setSigningOut(true);
    try {
      await logout();
      navigate('/login', { replace: true });
    } finally {
      setSigningOut(false);
    }
  }, [logout, navigate]);

  if (isLoading) {
    return null;
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (!pkiPending && uiState === 'success') {
    return <Navigate to={from} replace />;
  }

  const statusMessage = (() => {
    switch (uiState) {
      case 'waiting_token':
        return t('pki.statusWaitingToken');
      case 'select_cert':
        return t('pki.statusSelectCert');
      case 'verifying':
        return t('pki.statusVerifying');
      case 'success':
        return t('pki.statusSuccess');
      case 'error':
        return error ?? t('pki.verifyError');
      default:
        return '';
    }
  })();

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <div className={styles.shieldIcon} aria-hidden>
          <SafetyCertificateOutlined />
        </div>

        <Typography.Title level={3} style={{ textAlign: 'center' }}>
          {t('pki.title')}
        </Typography.Title>
        <Typography.Paragraph type="secondary" style={{ textAlign: 'center' }}>
          {t('pki.subtitle', { name: user.display_name })}
        </Typography.Paragraph>

        <Steps
          className={styles.steps}
          current={pkiPending ? 1 : 2}
          items={[
            { title: t('pki.stepLogin') },
            { title: t('pki.stepCert') },
            { title: t('pki.stepDone') },
          ]}
        />

        <div className={styles.statusBox} role="status" aria-live="polite">
          <Typography.Text>{statusMessage}</Typography.Text>
        </div>

        {error ? (
          <Alert
            type="error"
            message={error}
            showIcon
            className={styles.errorAlert}
            role="alert"
          />
        ) : null}

        <Typography.Text type="secondary">{t('pki.devHint')}</Typography.Text>

        <Upload
          accept=".pem,.crt,.cer"
          maxCount={1}
          fileList={certFile}
          beforeUpload={() => false}
          onChange={({ fileList, file }) => {
            setCertFile(fileList);
            setSelectedCert(file.originFileObj ?? null);
          }}
        >
          <Button block style={{ marginTop: 16 }}>
            {t('pki.selectCertificate')}
          </Button>
        </Upload>

        <Upload
          accept=".pem,.key"
          maxCount={1}
          fileList={keyFile}
          beforeUpload={() => false}
          onChange={({ fileList, file }) => {
            setKeyFile(fileList);
            setSelectedKey(file.originFileObj ?? null);
          }}
        >
          <Button block style={{ marginTop: 8 }}>
            {t('pki.selectPrivateKey')}
          </Button>
        </Upload>

        <div className={styles.actions}>
          <Button
            type="primary"
            block
            size="large"
            loading={uiState === 'verifying'}
            onClick={() => void handleVerify()}
          >
            {t('pki.verifyButton')}
          </Button>
          <Button
            block
            size="large"
            loading={signingOut}
            disabled={uiState === 'verifying'}
            onClick={() => void handleSignOut()}
            style={{ marginTop: 8 }}
          >
            {t('pki.signOutAndLogin')}
          </Button>
        </div>

        <button
          type="button"
          className={styles.helpLink}
          onClick={() => setHelpOpen(true)}
        >
          {t('pki.helpLink')}
        </button>

        <Modal
          title={t('pki.helpTitle')}
          open={helpOpen}
          onCancel={() => setHelpOpen(false)}
          footer={[
            <Button key="close" onClick={() => setHelpOpen(false)}>
              {t('pki.helpClose')}
            </Button>,
          ]}
        >
          <Typography.Paragraph>{t('pki.helpIntro')}</Typography.Paragraph>
          <Typography.Paragraph>
            <ol>
              <li>{t('pki.helpStep1')}</li>
              <li>{t('pki.helpStep2')}</li>
              <li>{t('pki.helpStep3')}</li>
              <li>{t('pki.helpStep4')}</li>
            </ol>
          </Typography.Paragraph>
        </Modal>
      </div>
    </div>
  );
}
