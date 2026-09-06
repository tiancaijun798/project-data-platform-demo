import { useState } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, Typography, Button, theme } from 'antd'
import {
  DashboardOutlined, UserOutlined, ShoppingOutlined,
  FunnelPlotOutlined, MonitorOutlined, CodeOutlined,
  MenuFoldOutlined, MenuUnfoldOutlined, DatabaseOutlined,
  ExperimentOutlined, NodeIndexOutlined, ApartmentOutlined,
  RobotOutlined, GlobalOutlined,
} from '@ant-design/icons'
import { useI18n } from '../i18n'

const { Header, Sider, Content } = Layout

export default function MainLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const { token } = theme.useToken()
  const { t, toggle } = useI18n()

  const menuItems = [
    { key: '/dashboard', icon: <DashboardOutlined />,  label: t('menu.dashboard') },
    { key: '/users',     icon: <UserOutlined />,       label: t('menu.users') },
    { key: '/products',  icon: <ShoppingOutlined />,    label: t('menu.products') },
    { key: '/funnel',    icon: <FunnelPlotOutlined />,  label: t('menu.funnel') },
    { type: 'divider' },
    { key: '/ai-lab',    icon: <RobotOutlined />,       label: t('menu.ai_lab') },
    { key: '/graph',     icon: <NodeIndexOutlined />,   label: t('menu.graph') },
    { key: '/lineage',   icon: <ApartmentOutlined />,   label: t('menu.lineage') },
    { key: '/mlflow',    icon: <ExperimentOutlined />,   label: t('menu.mlflow') },
    { type: 'divider' },
    { key: '/monitor',   icon: <MonitorOutlined />,     label: t('menu.monitor') },
    { key: '/query',     icon: <CodeOutlined />,        label: t('menu.query') },
  ]

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider trigger={null} collapsible collapsed={collapsed} theme="dark" width={220}
        style={{ borderRight: `1px solid ${token.colorBorderSecondary}`, background: token.colorBgContainer }}>
        <div style={{ height: 64, display: 'flex', alignItems: 'center', justifyContent: 'center',
          borderBottom: `1px solid ${token.colorBorderSecondary}`, gap: 8 }}>
          <DatabaseOutlined style={{ fontSize: 22, color: token.colorPrimary }} />
          {!collapsed && <Typography.Title level={4} style={{ margin: 0, color: token.colorPrimary }}>DataInsight</Typography.Title>}
        </div>
        <Menu theme="dark" mode="inline" selectedKeys={[location.pathname]} items={menuItems as any}
          onClick={({ key }) => navigate(key)} style={{ background: 'transparent', borderRight: 0, marginTop: 8 }} />
      </Sider>
      <Layout>
        <Header style={{ background: token.colorBgContainer, padding: '0 24px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          borderBottom: `1px solid ${token.colorBorderSecondary}`, height: 64 }}>
          <Button type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)} />
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <Typography.Text type="secondary">{t('app.title')} v2.0</Typography.Text>
            <Button size="small" icon={<GlobalOutlined />} onClick={toggle}>{t('lang.switch')}</Button>
          </div>
        </Header>
        <Content style={{ margin: 24, overflow: 'auto' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
