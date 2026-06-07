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
  DashboardOutlined,
  HeartOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuOutlined,
  MenuUnfoldOutlined,
  SettingOutlined,
  TeamOutlined,
  FileTextOutlined,
  AuditOutlined,
  CheckSquareOutlined,
  SwapOutlined,
} from '@ant-design/icons';
import { Button, Drawer, Dropdown, Grid, Layout, Menu, Segmented, Space, Tag } from 'antd';
import type { MenuProps } from 'antd';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '@/features/auth/useAuth';
import { navItemsForUser } from '@/features/auth/navConfig';
import { layout as layoutTokens } from '@/design-system/tokens';

import styles from './AppShell.module.css';

const { Header, Sider, Content } = Layout;
const SIDEBAR_STORAGE_KEY = 'portal.sidebar.collapsed';

const NAV_ICONS: Record<string, React.ReactNode> = {
  '/dashboard': <DashboardOutlined aria-hidden />,
  '/admin/settings': <SettingOutlined aria-hidden />,
  '/admin/departments': <TeamOutlined aria-hidden />,
  '/admin/users': <TeamOutlined aria-hidden />,
  '/cntt/templates': <FileTextOutlined aria-hidden />,
  '/cntt/approvals': <CheckSquareOutlined aria-hidden />,
  '/dept/templates': <FileTextOutlined aria-hidden />,
  '/dept/transactions': <SwapOutlined aria-hidden />,
  '/dept/approvals': <CheckSquareOutlined aria-hidden />,
  '/audit': <AuditOutlined aria-hidden />,
  '/health-ui': <HeartOutlined aria-hidden />,
};

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
      key: 'logout',
      icon: <LogoutOutlined />,
      label: t('auth.logout'),
      onClick: () => {
        void handleLogout();
      },
    },
  ];

  const appTitle = tenant?.branding?.app_name ?? t('app.name');
  const primaryColor = tenant?.branding?.primary_color;

  const sidebarContent = (
    <Menu
      theme="dark"
      mode="inline"
      selectedKeys={[selectedKey]}
      items={menuItems}
      onClick={handleMenuClick}
    />
  );

  return (
    <Layout className={styles.shell}>
      {!isMobile && (
        <Sider
          collapsible
          collapsed={collapsed}
          onCollapse={setCollapsed}
          width={layoutTokens.sidebarWidth}
          collapsedWidth={layoutTokens.sidebarCollapsedWidth}
          trigger={null}
        >
          {sidebarContent}
        </Sider>
      )}

      <Layout>
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
                onClick={toggleCollapsed}
              />
            )}
            <span
              className={styles.logoMark}
              style={primaryColor ? { background: primaryColor } : undefined}
              aria-hidden
            >
              P
            </span>
            <h1 className={styles.appTitle}>{appTitle}</h1>
            {tenant ? (
              <Tag className={styles.tenantBadge}>{tenant.name}</Tag>
            ) : null}
            {primaryDept ? (
              <Tag color="blue">{primaryDept.department_code}</Tag>
            ) : null}
          </div>

          <div className={styles.headerRight}>
            <Space size="small">
              <Segmented
                size="small"
                aria-label={t('header.language')}
                options={[
                  { label: 'vi', value: 'vi' },
                  { label: 'en', value: 'en' },
                ]}
                value={i18n.language.startsWith('vi') ? 'vi' : 'en'}
                onChange={(value) => {
                  void i18n.changeLanguage(String(value));
                }}
              />
              <Dropdown menu={{ items: userMenuItems }} trigger={['click']}>
                <Button type="text" aria-label={t('header.userMenu')}>
                  {user?.display_name ?? t('header.userMenu')}
                </Button>
              </Dropdown>
            </Space>
          </div>
        </Header>

        <Content>
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
      >
        {sidebarContent}
      </Drawer>
    </Layout>
  );
}
