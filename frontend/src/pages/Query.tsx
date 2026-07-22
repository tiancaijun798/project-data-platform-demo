import { useState } from 'react'
import { Card, Input, Button, Table, Spin, Typography, message, Row, Col } from 'antd'
import { SendOutlined, DownloadOutlined } from '@ant-design/icons'
import { api } from '../api'

const EXAMPLES = [
  'SELECT event_type, COUNT(*) as cnt FROM raw.user_events GROUP BY event_type ORDER BY cnt DESC',
  'SELECT user_segment, COUNT(*) as users, SUM(total_events) as events FROM public_clean.dim_users GROUP BY user_segment',
  'SELECT * FROM public_clean.fct_user_events_daily ORDER BY event_date DESC LIMIT 10',
  'SELECT * FROM public_clean.dim_products ORDER BY conversion_rate_pct DESC LIMIT 10',
]

export default function Query() {
  const [sql, setSql] = useState(EXAMPLES[0])
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  const runQuery = async () => {
    if (!sql.trim()) return
    setLoading(true)
    try {
      const res = await api.query(sql.trim())
      setResult(res)
    } catch {
      message.error('查询失败，请检查 SQL 语法')
    }
    setLoading(false)
  }

  const exportCSV = () => {
    if (!result?.columns || !result?.rows) return
    const header = result.columns.join(',')
    const body = result.rows.map((r: any) => result.columns.map((c: string) => JSON.stringify(r[c] ?? '')).join(',')).join('\n')
    const blob = new Blob(['﻿' + header + '\n' + body], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = 'query_result.csv'; a.click()
  }

  const columns = result?.columns?.map((c: string) => ({
    title: c, dataIndex: c, key: c, ellipsis: true,
    render: (v: any) => v === null ? <span style={{ color: '#666' }}>NULL</span> : String(v),
  })) || []

  return (
    <div>
      <Typography.Title level={3} style={{ marginBottom: 24 }}>数据查询</Typography.Title>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card title="SQL 编辑器" extra={
            <Button type="primary" icon={<SendOutlined />} onClick={runQuery} loading={loading}>执行</Button>
          }>
            <Input.TextArea
              value={sql}
              onChange={e => setSql(e.target.value)}
              rows={8}
              style={{ fontFamily: 'monospace', fontSize: 14 }}
              placeholder="输入 SQL 查询..."
            />
            <div style={{ marginTop: 12 }}>
              <Typography.Text type="secondary">示例查询：</Typography.Text>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
                {EXAMPLES.map((ex, i) => (
                  <Button key={i} size="small" onClick={() => setSql(ex)} type={sql === ex ? 'primary' : 'default'}>例 {i + 1}</Button>
                ))}
              </div>
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title="查询结果" extra={
            result && <Button icon={<DownloadOutlined />} size="small" onClick={exportCSV}>导出 CSV</Button>
          }>
            {loading ? <Spin /> : result ? (
              <div>
                <Typography.Text type="secondary">
                  {result.row_count} 行 · {result.elapsed_ms}ms
                </Typography.Text>
                <Table
                  columns={columns}
                  dataSource={result.rows?.map((r: any, i: number) => ({ ...r, _key: i }))}
                  rowKey="_key"
                  size="small"
                  scroll={{ x: 'max-content' }}
                  pagination={{ pageSize: 20 }}
                />
              </div>
            ) : (
              <Typography.Text type="secondary">选择示例查询或输入 SQL，点击"执行"查看结果</Typography.Text>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  )
}
