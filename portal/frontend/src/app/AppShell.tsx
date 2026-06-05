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
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  MenuOutlined,
} from '@ant-design/icons';
import { Button, Drawer, Grid, Layout, Menu, Segmented, Space } from 'antd';
import type { MenuProps } from 'antd';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';

import { layout as layoutTokens } from '@/design-system/tokens';

import styles from './AppShell.module.css';

const { Header, Sider, Content } = Layout;
const SIDEBAR_STORAGE_KEY = 'portal.sidebar.collapsed';

type NavKey = '/' | '/health-ui';

export function AppShell() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
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

  const selectedKey = useMemo<NavKey>(() => {
    if (location.pathname.startsWith('/health-ui')) {
      return '/health-ui';
    }
    return '/';
  }, [location.pathname]);

  const menuItems: MenuProps['items'] = [
    {
      key: '/',
      icon: <DashboardOutlined aria-hidden />,
      label: t('nav.overview'),
    },
    {
      key: '/health-ui',
      icon: <HeartOutlined aria-hidden />,
      label: t('nav.health'),
    },
  ];

  const handleMenuClick: MenuProps['onClick'] = ({ key }) => {
    navigate(key);
    if (isMobile) {
      setDrawerOpen(false);
    }
  };

  const toggleCollapsed = useCallback(() => {
    setCollapsed((prev) => !prev);
  }, []);

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
            <span className={styles.logoMark} aria-hidden>
              P
            </span>
            <h1 className={styles.appTitle}>{t('app.name')}</h1>
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
              <Button type="text" aria-label={t('header.userMenu')}>
                Demo User
              </Button>
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
        title={t('app.name')}
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
