import { Card, Col, Row, Spin, Typography, Tag, Table } from 'antd'
import { CheckCircleOutlined, CloseCircleOutlined, MinusCircleOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api'

export default function Monitor() {
  const { data, isLoading } = useQuery({ queryKey: ['services'], queryFn: api.services, refetchInterval: 10_000 })

  if (isLoading) return <Spin size="large" style={{ display: 'block', margin: '200px auto' }} />

  const services = data?.data || []

  const statusIcon = (s: string) => {
    if (s === 'running') return <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 28 }} />
    if (s === 'stopped') return <CloseCircleOutlined style={{ color: '#f5222d', fontSize: 28 }} />
    return <MinusCircleOutlined style={{ color: '#999', fontSize: 28 }} />
  }

  const columns = [
    { title: '服务', dataIndex: 'name', key: 'name' },
    { title: '状态', dataIndex: 'status', key: 'status',
      render: (s: string) => <Tag color={s === 'running' ? 'green' : 'red'}>{s}</Tag> },
    { title: '端口', dataIndex: 'port', key: 'port' },
    { title: '地址', dataIndex: 'url', key: 'url',
      render: (u: string) => <a href={u} target="_blank" rel="noopener noreferrer">{u}</a> },
  ]

  return (
    <div>
      <Typography.Title level={3} style={{ marginBottom: 24 }}>实时监控</Typography.Title>

      <Row gutter={[16, 16]}>
        {services.map((s: any) => (
          <Col xs={24} sm={12} lg={6} key={s.name}>
            <Card hoverable onClick={() => window.open(s.url, '_blank')}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <Typography.Text strong style={{ fontSize: 16 }}>{s.name}</Typography.Text>
                  <br />
                  <Tag color={s.status === 'running' ? 'green' : 'red'}>{s.status}</Tag>
                  <Typography.Text type="secondary"> :{s.port}</Typography.Text>
                </div>
                {statusIcon(s.status)}
              </div>
            </Card>
          </Col>
        ))}
      </Row>

      <Row style={{ marginTop: 24 }}>
        <Col span={24}>
          <Card title="Grafana 监控大屏">
            <iframe
              src="http://localhost:3000/d-solo/data-platform-monitor/data-platform-monitoring?orgId=1&refresh=10s&panelId=1&theme=dark"
              width="100%"
              height="400"
              style={{ border: 0, borderRadius: 8 }}
              title="Grafana"
            />
            <Typography.Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
              完整监控面板: <a href="http://localhost:3000" target="_blank" rel="noopener noreferrer">Grafana (admin/admin)</a>
            </Typography.Text>
          </Card>
        </Col>
      </Row>

      <Row style={{ marginTop: 16 }}>
        <Col span={24}>
          <Card title="服务清单">
            <Table dataSource={services} columns={columns} rowKey="name" size="small" pagination={false} />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
