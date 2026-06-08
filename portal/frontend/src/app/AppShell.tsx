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
import {
  AuditOutlined,
  CheckSquareOutlined,
  DashboardOutlined,
  FileTextOutlined,
  HeartOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuOutlined,
  MenuUnfoldOutlined,
  SettingOutlined,
  SwapOutlined,
  TeamOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { Avatar, Button, Drawer, Dropdown, Grid, Layout, Menu, Space } from 'antd';
import type { MenuProps } from 'antd';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';

import { ThemeProvider } from '@/design-system/ThemeProvider';
import { layout as layoutTokens } from '@/design-system/tokens';
import { PortalLogo } from '@/components/PortalLogo';
import { useAuth } from '@/features/auth/useAuth';
import { navItemsForUser } from '@/features/auth/navConfig';

import styles from './AppShell.module.css';

const { Header, Sider, Content } = Layout;
const SIDEBAR_STORAGE_KEY = 'portal.sidebar.collapsed';

const NAV_ICONS: Record<string, React.ReactNode> = {
  '/dashboard': <DashboardOutlined aria-hidden />,
  '/admin/settings': <SettingOutlined aria-hidden />,
  '/admin/departments': <TeamOutlined aria-hidden />,
  '/admin/users': <UserOutlined aria-hidden />,
  '/cntt/templates': <FileTextOutlined aria-hidden />,
  '/cntt/approvals': <CheckSquareOutlined aria-hidden />,
  '/dept/templates': <FileTextOutlined aria-hidden />,
  '/dept/transactions': <SwapOutlined aria-hidden />,
  '/dept/approvals': <CheckSquareOutlined aria-hidden />,
  '/audit': <AuditOutlined aria-hidden />,
  '/health-ui': <HeartOutlined aria-hidden />,
};

function userInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) {
    return '?';
  }
  const first = parts[0] ?? '';
  if (parts.length === 1) {
    return first.slice(0, 2).toUpperCase();
  }
  const last = parts[parts.length - 1] ?? '';
  return `${first[0] ?? ''}${last[0] ?? ''}`.toUpperCase() || '?';
}

export function AppShell() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const { user, tenant, logout } = useAuth();
  const primaryDept = user?.departments?.[0];
  const screens = Grid.useBreakpoint();
  const isMobile = !screens.md;

  const [collapsed, setCollapsed] = useState(() => {
    const stored = localStorage.getItem(SIDEBAR_STORAGE_KEY);
    return stored === 'true';
  });
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    localStorage.setItem(SIDEBAR_STORAGE_KEY, String(collapsed));
  }, [collapsed]);

  const allowedNav = useMemo(
    () => (user ? navItemsForUser(user) : []),
    [user],
  );

  const selectedKey = useMemo(() => {
    const match = allowedNav.find((item) =>
      item.key === '/dashboard'
        ? location.pathname === '/dashboard' || location.pathname === '/'
        : location.pathname.startsWith(item.key),
    );
    return match?.key ?? '/dashboard';
  }, [allowedNav, location.pathname]);

  const menuItems: MenuProps['items'] = allowedNav.map((item) => ({
    key: item.key,
    icon: NAV_ICONS[item.key] ?? <DashboardOutlined aria-hidden />,
    label: t(item.labelKey),
  }));

  const handleMenuClick: MenuProps['onClick'] = ({ key }) => {
    navigate(key);
    if (isMobile) {
      setDrawerOpen(false);
    }
  };

  const toggleCollapsed = useCallback(() => {
    setCollapsed((prev) => !prev);
  }, []);

  const handleLogout = useCallback(async () => {
    await logout();
    navigate('/login', { replace: true });
  }, [logout, navigate]);

  const userMenuItems: MenuProps['items'] = [
    {
      key: 'profile',
      label: (
        <div className={styles.userMenuHeader}>
          <strong>{user?.display_name}</strong>
          {tenant ? <span>{tenant.name}</span> : null}
          {primaryDept ? (
            <span>
              {primaryDept.department_code} ·{' '}
              {t(`adminUsers.deptRole.${primaryDept.role}`)}
            </span>
          ) : null}
        </div>
      ),
      disabled: true,
    },
    { type: 'divider' },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: t('auth.logout'),
      danger: true,
      onClick: () => {
        void handleLogout();
      },
    },
  ];

  const appTitle = tenant?.branding?.app_name ?? t('app.name');
  const primaryColor = tenant?.branding?.primary_color;
  const logoUrl = tenant?.branding?.logo_url;

  const sidebarContent = (
    <>
      <div className={`${styles.sidebarBrand} ${collapsed ? styles.sidebarBrandCollapsed : ''}`}>
        {logoUrl ? (
          <img src={logoUrl} alt="" className={styles.sidebarLogo} />
        ) : (
          <PortalLogo
            size={collapsed ? 'sm' : 'md'}
            accentColor={primaryColor}
            className={styles.sidebarLogoMark}
          />
        )}
        {!collapsed ? (
          <div className={styles.sidebarBrandText}>
            <span className={styles.sidebarAppName}>{appTitle}</span>
            {tenant ? <span className={styles.sidebarTenant}>{tenant.name}</span> : null}
          </div>
        ) : null}
      </div>
      <Menu
        mode="inline"
        selectedKeys={[selectedKey]}
        items={menuItems}
        onClick={handleMenuClick}
        className={styles.sidebarMenu}
      />
    </>
  );

  return (
    <ThemeProvider branding={tenant?.branding}>
      <Layout className={styles.shell}>
        {!isMobile && (
          <Sider
            collapsible
            collapsed={collapsed}
            onCollapse={setCollapsed}
            width={layoutTokens.sidebarWidth}
            collapsedWidth={layoutTokens.sidebarCollapsedWidth}
            trigger={null}
            className={styles.sider}
          >
            {sidebarContent}
          </Sider>
        )}

        <Layout className={styles.mainLayout}>
          <Header className={styles.header}>
            <div className={styles.headerLeft}>
              {isMobile ? (
                <Button
                  type="text"
                  icon={<MenuOutlined />}
                  aria-label={t('common.openMenu')}
                  className={styles.mobileMenuButton}
                  onClick={() => setDrawerOpen(true)}
                />
              ) : (
                <Button
                  type="text"
                  icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
                  aria-label={
                    collapsed ? t('common.expandSidebar') : t('common.collapseSidebar')
                  }
                  className={styles.collapseButton}
                  onClick={toggleCollapsed}
                />
              )}
              {isMobile ? (
                <span className={styles.mobileTitle}>{appTitle}</span>
              ) : null}
            </div>

            <div className={styles.headerRight}>
              <Space size="middle">
                <div className={styles.langSwitch} role="group" aria-label={t('header.language')}>
                  {(['vi', 'en'] as const).map((lang) => (
                    <button
                      key={lang}
                      type="button"
                      className={`${styles.langButton} ${
                        (lang === 'vi' && i18n.language.startsWith('vi')) ||
                        (lang === 'en' && !i18n.language.startsWith('vi'))
                          ? styles.langButtonActive
                          : ''
                      }`}
                      onClick={() => {
                        void i18n.changeLanguage(lang);
                      }}
                    >
                      {lang.toUpperCase()}
                    </button>
                  ))}
                </div>
                <Dropdown menu={{ items: userMenuItems }} trigger={['click']}>
                  <button
                    type="button"
                    className={styles.userButton}
                    aria-label={t('header.userMenu')}
                  >
                    <Avatar
                      size={36}
                      className={styles.userAvatar}
                      style={primaryColor ? { background: primaryColor } : undefined}
                    >
                      {user?.display_name ? userInitials(user.display_name) : '?'}
                    </Avatar>
                    {!isMobile && user?.display_name ? (
                      <span className={styles.userName}>{user.display_name}</span>
                    ) : null}
                  </button>
                </Dropdown>
              </Space>
            </div>
          </Header>

          <Content className={styles.content}>
            <div className={styles.contentWrapper}>
              <Outlet />
            </div>
          </Content>
        </Layout>

        <Drawer
          title={appTitle}
          placement="left"
          onClose={() => setDrawerOpen(false)}
          open={drawerOpen}
          styles={{ body: { padding: 0 } }}
          className={styles.mobileDrawer}
        >
          {sidebarContent}
        </Drawer>
      </Layout>
    </ThemeProvider>
  );
}
