import { Card, Col, Row, Spin, Typography, Statistic } from 'antd'
import { useQuery } from '@tanstack/react-query'
import ReactECharts from 'echarts-for-react'
import { api } from '../api'

export default function Funnel() {
  const { data, isLoading } = useQuery({ queryKey: ['funnel'], queryFn: api.funnel })

  if (isLoading) return <Spin size="large" style={{ display: 'block', margin: '200px auto' }} />

  const steps = data?.data || []
  const total = steps[0]?.value || 1

  const funnelOption = {
    tooltip: { trigger: 'item' },
    series: [{
      type: 'funnel', left: '10%', top: 20, bottom: 20, width: '80%',
      min: 0, max: total, sort: 'descending', gap: 2,
      label: { show: true, position: 'inside', color: '#fff', formatter: (p: any) => `${p.name}\n${p.value?.toLocaleString()}` },
      itemStyle: { borderColor: '#141414', borderWidth: 0 },
      data: steps.map((s: any) => ({
        name: s.name,
        value: s.value,
        itemStyle: { color: ['#1677ff', '#69b1ff', '#91caff', '#bae0ff', '#d6e4ff'][steps.indexOf(s)] || '#1677ff' },
      })),
    }],
  }

  return (
    <div>
      <Typography.Title level={3} style={{ marginBottom: 24 }}>转化漏斗</Typography.Title>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          <Card title="用户行为转化漏斗">
            <ReactECharts option={funnelOption} style={{ height: 450 }} />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="转化率明细">
            {steps.map((s: any, i: number) => {
              const rate = i === 0 ? 100 : ((s.value / steps[0]?.value) * 100).toFixed(1)
              const prevRate = i === 0 ? null : ((s.value / steps[i - 1]?.value) * 100).toFixed(1)
              return (
                <Card key={s.name} size="small" style={{ marginBottom: 12 }}>
                  <Statistic
                    title={`${s.name}`}
                    value={s.value}
                    suffix={
                      <span style={{ fontSize: 14 }}>
                        <span style={{ color: '#999' }}>（占第一步 {rate}%）</span>
                        {prevRate && <span style={{ color: '#52c41a', marginLeft: 8 }}>环比 {prevRate}%</span>}
                      </span>
                    }
                  />
                </Card>
              )
            })}
          </Card>
        </Col>
      </Row>
    </div>
  )
}
