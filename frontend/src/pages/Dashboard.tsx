import { Card, Col, Row, Statistic, Spin, Typography } from 'antd'
import { ArrowUpOutlined, ShoppingCartOutlined, UserOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import ReactECharts from 'echarts-for-react'
import { api } from '../api'

export default function Dashboard() {
  const { data: dash, isLoading } = useQuery({ queryKey: ['dashboard'], queryFn: api.dashboard })
  const { data: trend }   = useQuery({ queryKey: ['salesTrend'], queryFn: api.salesTrend })
  const { data: heatmap } = useQuery({ queryKey: ['hourlyHeatmap'], queryFn: api.hourlyHeatmap })

  if (isLoading) return <Spin size="large" style={{ display: 'block', margin: '200px auto' }} />

  const stats = dash?.data || {}

  const trendOption = {
    tooltip: { trigger: 'axis' },
    legend: { data: ['事件数', '购买数'], textStyle: { color: '#999' } },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: trend?.data?.map((d: any) => d.date) || [], axisLabel: { color: '#999' } },
    yAxis: { type: 'value', axisLabel: { color: '#999' } },
    series: [
      { name: '事件数', type: 'line', data: trend?.data?.map((d: any) => d.events) || [], smooth: true, itemStyle: { color: '#1677ff' }, areaStyle: { color: 'rgba(22,119,255,0.1)' } },
      { name: '购买数', type: 'line', data: trend?.data?.map((d: any) => d.purchases) || [], smooth: true, itemStyle: { color: '#52c41a' } },
    ],
  }

  const heatOption = {
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: heatmap?.data?.map((d: any) => `${d.hour}:00`) || [], axisLabel: { color: '#999' } },
    yAxis: { type: 'value', axisLabel: { color: '#999' } },
    series: [{
      name: '事件数', type: 'bar',
      data: heatmap?.data?.map((d: any) => d.events) || [],
      itemStyle: { color: '#1677ff', borderRadius: [4, 4, 0, 0] },
    }],
  }

  return (
    <div>
      <Typography.Title level={3} style={{ marginBottom: 24 }}>销售大盘</Typography.Title>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card><Statistic title="今日事件数" value={stats.total_events || 0} prefix={<ThunderboltOutlined />} suffix="条" /></Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card><Statistic title="今日订单数" value={stats.today_orders || 0} prefix={<ShoppingCartOutlined />} suffix="单" valueStyle={{ color: '#52c41a' }} /></Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card><Statistic title="活跃用户" value={stats.today_users || 0} prefix={<UserOutlined />} suffix="人" /></Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card><Statistic title="转化率" value={stats.conversion_rate || 0} prefix={<ArrowUpOutlined />} suffix="%" precision={1} valueStyle={{ color: '#faad14' }} /></Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={14}>
          <Card title="近 7 天趋势">
            <ReactECharts option={trendOption} style={{ height: 350 }} />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="时段热力图">
            <ReactECharts option={heatOption} style={{ height: 350 }} />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
