import { Card, Col, Row, Table, Spin, Typography } from 'antd'
import { useQuery } from '@tanstack/react-query'
import ReactECharts from 'echarts-for-react'
import { api } from '../api'

export default function Products() {
  const { data: rank, isLoading: rLoading } = useQuery({ queryKey: ['productRank'], queryFn: api.productRank })
  const { data: share } = useQuery({ queryKey: ['categoryShare'], queryFn: api.categoryShare })

  const products = rank?.data || []
  const categories = share?.data || []

  const barOption = {
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: products.slice(0, 10).map((p: any) => p.product_id), axisLabel: { color: '#999', rotate: 30 } },
    yAxis: { type: 'value', axisLabel: { color: '#999' } },
    series: [
      { name: '浏览量', type: 'bar', data: products.slice(0, 10).map((p: any) => p.total_views), itemStyle: { color: '#1677ff', borderRadius: [4,4,0,0] } },
      { name: '购买量', type: 'bar', data: products.slice(0, 10).map((p: any) => p.total_purchases), itemStyle: { color: '#52c41a', borderRadius: [4,4,0,0] } },
    ],
  }

  const pieOption = {
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie', radius: '70%',
      data: categories.map((c: any) => ({ name: c.category, value: c.views })),
      label: { color: '#999' },
    }],
  }

  const columns = [
    { title: '商品 ID', dataIndex: 'product_id', key: 'product_id' },
    { title: '品类', dataIndex: 'category', key: 'category' },
    { title: '浏览量', dataIndex: 'total_views', key: 'total_views', sorter: (a: any, b: any) => a.total_views - b.total_views },
    { title: '购买量', dataIndex: 'total_purchases', key: 'total_purchases', sorter: (a: any, b: any) => a.total_purchases - b.total_purchases },
    { title: '转化率', dataIndex: 'conversion_rate', key: 'conversion_rate',
      render: (v: number) => <span style={{ color: v > 3 ? '#52c41a' : '#faad14' }}>{v}%</span>,
      sorter: (a: any, b: any) => a.conversion_rate - b.conversion_rate },
  ]

  if (rLoading) return <Spin size="large" style={{ display: 'block', margin: '200px auto' }} />

  return (
    <div>
      <Typography.Title level={3} style={{ marginBottom: 24 }}>商品分析</Typography.Title>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          <Card title="商品热榜 Top 10">
            <ReactECharts option={barOption} style={{ height: 350 }} />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="品类销售占比">
            <ReactECharts option={pieOption} style={{ height: 350 }} />
          </Card>
        </Col>
      </Row>
      <Row style={{ marginTop: 16 }}>
        <Col span={24}>
          <Card title="全部商品排行">
            <Table dataSource={products} columns={columns} rowKey="product_id" size="small"
              pagination={{ pageSize: 20 }} loading={rLoading} />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
