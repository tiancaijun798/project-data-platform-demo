import { Card, Col, Row, Statistic, Spin, Typography } from 'antd'
import { ArrowUpOutlined, ShoppingCartOutlined, UserOutlined, ThunderboltOutlined, DatabaseOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import ReactECharts from 'echarts-for-react'
import { api } from '../api'
import { useI18n } from '../i18n'

export default function Dashboard() {
  const { t } = useI18n()
  const { data: dash, isLoading } = useQuery({ queryKey: ['dashboard'], queryFn: api.dashboard })
  const { data: trend }   = useQuery({ queryKey: ['salesTrend'], queryFn: api.salesTrend })
  const { data: heatmap } = useQuery({ queryKey: ['hourlyHeatmap'], queryFn: api.hourlyHeatmap })
  const { data: overview } = useQuery({ queryKey: ['dataOverview'], queryFn: api.dataOverview })

  if (isLoading) return <Spin size="large" style={{ display: 'block', margin: '200px auto' }} />

  const stats = dash?.data || {}
  const ov = overview?.data || {}

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
      <Typography.Title level={3}>{t('dashboard.title')}</Typography.Title>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card><Statistic title={t('dashboard.total_events')} value={stats.total_events || 0} prefix={<ThunderboltOutlined />} suffix="条" /></Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card><Statistic title={t('dashboard.total_orders')} value={stats.today_orders || 0} prefix={<ShoppingCartOutlined />} suffix="单" valueStyle={{ color: '#52c41a' }} /></Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card><Statistic title={t('dashboard.active_users')} value={stats.today_users || 0} prefix={<UserOutlined />} suffix="人" /></Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card><Statistic title={t('dashboard.conversion_rate')} value={stats.conversion_rate || 0} prefix={<ArrowUpOutlined />} suffix="%" precision={1} valueStyle={{ color: '#faad14' }} /></Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={24}>
          <Card title={t('dashboard.data_scale')}>
            <Row gutter={16}>
              <Col span={6}><Statistic title="PostgreSQL" value={(ov.postgres_events || 0).toLocaleString()} prefix={<DatabaseOutlined />} suffix="events" /></Col>
              <Col span={6}><Statistic title="Milvus" value={(ov.milvus_event_vectors || 0).toLocaleString()} prefix={<DatabaseOutlined />} suffix="vectors" /></Col>
              <Col span={6}><Statistic title="Neo4j" value={`${(ov.neo4j_users || 0)}U/${(ov.neo4j_events || 0)}E/${(ov.neo4j_products || 0)}P`} prefix={<DatabaseOutlined />} /></Col>
              <Col span={6}><Statistic title="FAISS (RAG)" value={(ov.faiss_vectors || 0).toLocaleString()} prefix={<DatabaseOutlined />} suffix="vectors" /></Col>
            </Row>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={14}>
          <Card title={t('dashboard.trend')}>
            <ReactECharts option={trendOption} style={{ height: 350 }} />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title={t('dashboard.heatmap')}>
            <ReactECharts option={heatOption} style={{ height: 350 }} />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
