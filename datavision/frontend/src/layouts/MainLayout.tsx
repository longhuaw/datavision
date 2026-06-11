import { useState, useEffect } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Button, Dropdown, Avatar, Space, theme, Switch, Modal } from 'antd';
import {
  DashboardOutlined,
  BarChartOutlined,
  DatabaseOutlined,
  TableOutlined,
  RobotOutlined,
  SettingOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  UserOutlined,
  LogoutOutlined,
  SunOutlined,
  MoonOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import type { MenuProps } from 'antd';
import { useAuthStore, useAppStore } from '@/store';
import { useEffect as useInitEffect } from 'react';
import api from '@/services/api';

const { Header, Sider, Content } = Layout;

const menuItems: MenuProps['items'] = [
  { key: '/dashboards', icon: <DashboardOutlined />, label: '看板管理' },
  { key: '/charts', icon: <BarChartOutlined />, label: '图表工作台' },
  { key: '/datasources', icon: <DatabaseOutlined />, label: '数据源' },
  { key: '/datasets', icon: <TableOutlined />, label: '数据集' },
  { key: '/ai', icon: <RobotOutlined />, label: 'AI 助手' },
  { key: '/system', icon: <SettingOutlined />, label: '系统管理' },
];

export default function MainLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const { theme: themeMode, setTheme } = useAppStore();
  const { token: antdToken } = theme.useToken();

  // 加载用户信息
  useInitEffect(() => {
    if (!user) {
      api.get('/auth/me').then((res) => {
        useAuthStore.getState().updateUser(res.data.data);
      }).catch(() => {});
    }
  });

  const selectedKey = '/' + location.pathname.split('/')[1] || '/dashboards';

  const handleMenuClick: MenuProps['onClick'] = ({ key }) => {
    navigate(key);
  };

  const handleLogout = () => {
    Modal.confirm({
      title: '确认退出',
      content: '确定要退出登录吗？',
      onOk: () => {
        logout();
        navigate('/login');
      },
    });
  };

  const userMenuItems: MenuProps['items'] = [
    { key: 'profile', icon: <UserOutlined />, label: '个人信息' },
    { key: 'theme', icon: themeMode === 'dark' ? <SunOutlined /> : <MoonOutlined />,
      label: themeMode === 'dark' ? '切换亮色主题' : '切换暗色主题',
      onClick: () => setTheme(themeMode === 'dark' ? 'light' : 'dark'),
    },
    { type: 'divider' },
    { key: 'logout', icon: <LogoutOutlined />, label: '退出登录', danger: true,
      onClick: handleLogout,
    },
  ];

  return (
    <Layout style={{ height: '100vh' }}>
      {/* 左侧导航 */}
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        width={220}
        style={{
          borderRight: '1px solid ' + (themeMode === 'dark' ? '#303030' : '#f0f0f0'),
        }}
      >
        {/* Logo */}
        <div
          style={{
            height: 56,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderBottom: '1px solid ' + (themeMode === 'dark' ? '#303030' : '#f0f0f0'),
          }}
        >
          <ThunderboltOutlined style={{ fontSize: 22, color: antdToken.colorPrimary, marginRight: collapsed ? 0 : 10 }} />
          {!collapsed && (
            <span style={{ fontSize: 18, fontWeight: 700, letterSpacing: 1 }}>
              DataVision
            </span>
          )}
        </div>

        <Menu
          theme={themeMode === 'dark' ? 'dark' : 'light'}
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={handleMenuClick}
          style={{ borderInlineEnd: 'none', marginTop: 8 }}
        />
      </Sider>

      <Layout>
        {/* 顶部栏 */}
        <Header
          style={{
            padding: '0 24px',
            height: 56,
            lineHeight: '56px',
            background: themeMode === 'dark' ? '#141414' : '#fff',
            borderBottom: '1px solid ' + (themeMode === 'dark' ? '#303030' : '#f0f0f0'),
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
            style={{ fontSize: 16, width: 40, height: 40 }}
          />

          <Space size={16}>
            <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
              <Space style={{ cursor: 'pointer' }}>
                <Avatar size="small" icon={<UserOutlined />} style={{ backgroundColor: antdToken.colorPrimary }} />
                <span>{user?.nickname || user?.username || '用户'}</span>
              </Space>
            </Dropdown>
          </Space>
        </Header>

        {/* 内容区 */}
        <Content
          style={{
            margin: 0,
            padding: 0,
            overflow: 'auto',
            background: themeMode === 'dark' ? '#000' : '#f5f5f5',
          }}
        >
          <div className="dv-fade-in">
            <Outlet />
          </div>
        </Content>
      </Layout>
    </Layout>
  );
}
