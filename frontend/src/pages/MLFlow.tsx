import { Card, Typography, Spin, Table, Tag, Statistic, Row, Col } from 'antd'
import { ExperimentOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { aiApi } from '../api/ai'
import { useI18n } from '../i18n'

export default function MLFlow() {
  const { t } = useI18n()
  const { data, isLoading } = useQuery({ queryKey: ['mlflowExps'], queryFn: aiApi.mlflowExperiments })

  const exps = data?.experiments || []
  const totalExps = exps.length
  const totalRuns = exps.reduce((s: number, e: any) => s + (e.run_count || 0), 0)

  const cols = [
    { title: 'ID', dataIndex: 'experiment_id', key: 'id' },
    { title: 'Name', dataIndex: 'name', key: 'name' },
    { title: 'Runs', dataIndex: 'run_count', key: 'runs', render: (c: number) => <Tag color="blue">{c}</Tag> },
  ]

  return (
    <div>
      <Typography.Title level={3}>{t('mlflow.title')}</Typography.Title>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={8}>
          <Card>
            <Row gutter={16}>
              <Col span={12}><Statistic title="Experiments" value={totalExps} prefix={<ExperimentOutlined />} /></Col>
              <Col span={12}><Statistic title="Total Runs" value={totalRuns} /></Col>
            </Row>
          </Card>
          {isLoading ? <Spin style={{ marginTop: 16 }} /> : (
            <Table dataSource={exps} columns={cols} rowKey="experiment_id" size="small" style={{ marginTop: 16 }} />
          )}
          <Typography.Link href="/mlflow/" target="_blank" style={{ display: 'block', marginTop: 12 }}>
            Open MLflow UI →
          </Typography.Link>
        </Col>
        <Col xs={24} lg={16}>
          <Card title="MLflow Tracking Server">
            <iframe
              src="/mlflow/"
              width="100%" height="500"
              style={{ border: 0, borderRadius: 8 }}
              title="MLflow"
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}
