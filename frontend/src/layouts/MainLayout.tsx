import { useState } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, Typography, Button, theme } from 'antd'
import {
  DashboardOutlined, UserOutlined, ShoppingOutlined,
  FunnelPlotOutlined, MonitorOutlined, CodeOutlined,
  MenuFoldOutlined, MenuUnfoldOutlined, DatabaseOutlined,
} from '@ant-design/icons'

const { Header, Sider, Content } = Layout

const menuItems = [
  { key: '/dashboard', icon: <DashboardOutlined />, label: '销售大盘' },
  { key: '/users',     icon: <UserOutlined />,      label: '用户分析' },
  { key: '/products',  icon: <ShoppingOutlined />,   label: '商品分析' },
  { key: '/funnel',    icon: <FunnelPlotOutlined />, label: '转化漏斗' },
  { key: '/monitor',   icon: <MonitorOutlined />,    label: '实时监控' },
  { key: '/query',     icon: <CodeOutlined />,       label: '数据查询' },
]

export default function MainLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const { token } = theme.useToken()

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        theme="dark"
        width={220}
        style={{
          borderRight: `1px solid ${token.colorBorderSecondary}`,
          background: token.colorBgContainer,
        }}
      >
        <div style={{
          height: 64, display: 'flex', alignItems: 'center', justifyContent: 'center',
          borderBottom: `1px solid ${token.colorBorderSecondary}`, gap: 8,
        }}>
          <DatabaseOutlined style={{ fontSize: 22, color: token.colorPrimary }} />
          {!collapsed && <Typography.Title level={4} style={{ margin: 0, color: token.colorPrimary }}>DataInsight</Typography.Title>}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ background: 'transparent', borderRight: 0, marginTop: 8 }}
        />
      </Sider>

      <Layout>
        <Header style={{
          background: token.colorBgContainer, padding: '0 24px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          borderBottom: `1px solid ${token.colorBorderSecondary}`, height: 64,
        }}>
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
          />
          <Typography.Text type="secondary">
            Data Platform Demo — 电商数据洞察平台 v1.0
          </Typography.Text>
        </Header>

        <Content style={{ margin: 24, overflow: 'auto' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
