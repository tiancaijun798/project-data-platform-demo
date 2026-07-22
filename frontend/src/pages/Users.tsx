import { Card, Col, Row, Table, Spin, Typography, Tag } from 'antd'
import { useQuery } from '@tanstack/react-query'
import ReactECharts from 'echarts-for-react'
import { api } from '../api'

const SEG_COLORS: Record<string, string> = { power_user: '#f50', active: '#1677ff', regular: '#52c41a', new: '#999' }

export default function Users() {
  const { data: seg, isLoading: sLoading } = useQuery({ queryKey: ['userSegments'], queryFn: api.userSegments })
  const { data: top, isLoading: tLoading } = useQuery({ queryKey: ['topUsers'], queryFn: api.topUsers })

  if (sLoading) return <Spin size="large" style={{ display: 'block', margin: '200px auto' }} />

  const segments = seg?.data || []
  const topUsers = top?.data || []

  const pieOption = {
    tooltip: { trigger: 'item' },
    legend: { orient: 'vertical', left: 'left', textStyle: { color: '#999' } },
    series: [{
      type: 'pie', radius: ['45%', '75%'], center: ['55%', '50%'],
      data: segments.map((s: any) => ({ name: s.segment, value: s.users })),
      label: { color: '#999' },
      itemStyle: { borderRadius: 4, borderColor: '#141414', borderWidth: 2 },
    }],
  }

  const columns = [
    { title: '用户 ID', dataIndex: 'user_id', key: 'user_id' },
    { title: '分群', dataIndex: 'segment', key: 'segment',
      render: (s: string) => <Tag color={SEG_COLORS[s]}>{s}</Tag> },
    { title: '总事件', dataIndex: 'total_events', key: 'total_events', sorter: (a: any, b: any) => a.total_events - b.total_events },
    { title: '最早活跃', dataIndex: 'first_seen', key: 'first_seen' },
    { title: '最近活跃', dataIndex: 'last_seen', key: 'last_seen' },
  ]

  return (
    <div>
      <Typography.Title level={3} style={{ marginBottom: 24 }}>用户分析</Typography.Title>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={10}>
          <Card title="用户分群">
            <ReactECharts option={pieOption} style={{ height: 320 }} />
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 16 }}>
              {segments.map((s: any) => (
                <Card key={s.segment} size="small" style={{ flex: 1, minWidth: 120 }}>
                  <Tag color={SEG_COLORS[s.segment]}>{s.segment}</Tag>
                  <div style={{ fontSize: 20, fontWeight: 700, marginTop: 8 }}>{s.users}<span style={{ fontSize: 13, color: '#999' }}> 人</span></div>
                  <div style={{ color: '#999', fontSize: 12 }}>{s.pct}% · {s.events} 事件</div>
                </Card>
              ))}
            </div>
          </Card>
        </Col>
        <Col xs={24} lg={14}>
          <Card title={`活跃用户排行榜 (${topUsers.length})`}>
            <Table dataSource={topUsers} columns={columns} rowKey="user_id" size="small"
              pagination={{ pageSize: 15 }} loading={tLoading} />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
