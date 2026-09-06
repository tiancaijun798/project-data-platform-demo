import { useState } from 'react'
import { Card, Input, Spin, Typography, Row, Col, Tag, Table, Statistic } from 'antd'
import { NodeIndexOutlined, BranchesOutlined, ApartmentOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { aiApi } from '../api/ai'
import { useI18n } from '../i18n'

export default function Graph() {
  const { t } = useI18n()
  const [pathUser, setPathUser] = useState('U0001')

  const { data: stats, isLoading } = useQuery({ queryKey: ['graphStats'], queryFn: aiApi.graphStats })
  const { data: path, isLoading: pLoading, refetch } = useQuery({
    queryKey: ['graphPath', pathUser], queryFn: () => aiApi.graphPath(pathUser), enabled: !!pathUser,
  })

  const nodeCols = [
    { title: 'Type', dataIndex: 'label', key: 'label', render: (l: string) => <Tag>{l}</Tag> },
    { title: 'Count', dataIndex: 'count', key: 'count' },
  ]
  const pathCols = [
    { title: 'Event', dataIndex: 'event_type', key: 'et', render: (et: string) => <Tag color="blue">{et}</Tag> },
    { title: 'Device', dataIndex: 'device', key: 'device' },
    { title: 'Product', dataIndex: 'product_id', key: 'pid' },
    { title: 'Category', dataIndex: 'category', key: 'cat' },
  ]

  const totalNodes = stats?.nodes?.reduce((s: number, n: any) => s + n.count, 0) || 0
  const totalRels = stats?.relationships?.reduce((s: number, r: any) => s + r.count, 0) || 0

  return (
    <div>
      <Typography.Title level={3}>{t('graph.title')}</Typography.Title>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={8}>
          <Card title={<><ApartmentOutlined /> {t('graph.stats')}</>}>
            {isLoading ? <Spin /> : (
              <>
                <Row gutter={16}>
                  <Col span={12}><Statistic title="Nodes" value={totalNodes} prefix={<NodeIndexOutlined />} /></Col>
                  <Col span={12}><Statistic title="Relationships" value={totalRels} prefix={<BranchesOutlined />} /></Col>
                </Row>
                <Table dataSource={stats?.nodes || []} columns={nodeCols} rowKey="label" size="small" pagination={false} style={{ marginTop: 16 }} />
              </>
            )}
          </Card>
        </Col>
        <Col xs={24} lg={16}>
          <Card title={<>{t('graph.user_path')}</>}
            extra={
              <Input.Search size="small" placeholder={t('graph.path_placeholder')} value={pathUser}
                onChange={(e) => setPathUser(e.target.value)} onSearch={() => { setPathUser(pathUser); refetch() }}
                enterButton="Go" style={{ width: 240 }} />
            }>
            {pLoading ? <Spin /> : (
              <Table dataSource={path?.path || []} columns={pathCols} rowKey={(_, i) => String(i)} size="small"
                pagination={false} locale={{ emptyText: 'No path data' }} />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  )
}
