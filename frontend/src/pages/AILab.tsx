import { useState } from 'react'
import { Card, Input, Typography, Row, Col, Tag, List, Divider } from 'antd'
import { SearchOutlined, RobotOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { useMutation } from '@tanstack/react-query'
import { aiApi } from '../api/ai'
import { useI18n } from '../i18n'

export default function AILab() {
  const { t } = useI18n()
  const [searchQ, setSearchQ] = useState('')
  const [ragQ, setRagQ] = useState('')
  const [searchResult, setSearchResult] = useState<any>(null)
  const [ragResult, setRagResult] = useState<any>(null)

  const vecMut = useMutation({
    mutationFn: (q: string) => aiApi.vectorSearch(q, 5),
    onSuccess: (data) => setSearchResult(data),
  })

  const ragMut = useMutation({
    mutationFn: (q: string) => aiApi.ragQuery(q, 5),
    onSuccess: (data) => setRagResult(data),
  })

  return (
    <div>
      <Typography.Title level={3}>{t('ai.title')}</Typography.Title>

      <Row gutter={[16, 16]}>
        {/* Vector Search */}
        <Col xs={24} lg={12}>
          <Card
            title={<><SearchOutlined /> {t('ai.vector_search')}</>}
            extra={<Tag color="blue">Milvus</Tag>}
          >
            <Input.Search
              placeholder={t('ai.search_placeholder')}
              value={searchQ}
              onChange={(e) => setSearchQ(e.target.value)}
              onSearch={() => vecMut.mutate(searchQ)}
              enterButton={t('ai.search_btn')}
              loading={vecMut.isPending}
              allowClear
            />
            {searchResult && !searchResult.error && (
              <div style={{ marginTop: 16 }}>
                <Typography.Text type="secondary">
                  {t('ai.elapsed')}: {searchResult.elapsed_ms}ms
                  | {t('ai.score')}: {searchResult.total} vectors
                </Typography.Text>
                <List size="small" style={{ marginTop: 8 }}
                  dataSource={searchResult.results || []}
                  renderItem={(item: any) => (
                    <List.Item>
                      <List.Item.Meta
                        title={<><Tag>{item.event_type}</Tag> User: {item.user_id} | Product: {item.product_id}</>}
                        description={<><Typography.Text type="secondary">score: {item.score}</Typography.Text><br />{item.text}</>}
                      />
                    </List.Item>
                  )}
                  locale={{ emptyText: t('ai.no_results') }}
                />
              </div>
            )}
            {searchResult?.error && <Typography.Text type="danger" style={{ marginTop: 8, display: 'block' }}>{searchResult.error}</Typography.Text>}
          </Card>
        </Col>

        {/* RAG Q&A */}
        <Col xs={24} lg={12}>
          <Card
            title={<><RobotOutlined /> {t('ai.rag_qa')}</>}
            extra={<Tag color="green">FAISS + DeepSeek</Tag>}
          >
            <Input.Search
              placeholder={t('ai.ask_placeholder')}
              value={ragQ}
              onChange={(e) => setRagQ(e.target.value)}
              onSearch={() => ragMut.mutate(ragQ)}
              enterButton={t('ai.ask_btn')}
              loading={ragMut.isPending}
              allowClear
            />
            {ragResult && !ragResult.error && (
              <div style={{ marginTop: 16 }}>
                <Typography.Text type="secondary">
                  {t('ai.elapsed')}: {ragResult.retrieval_ms}ms (retrieval) + {ragResult.generation_ms}ms (LLM)
                  | Model: {ragResult.model}
                </Typography.Text>
                <Divider style={{ margin: '12px 0' }} />
                <Typography.Paragraph style={{ background: '#f6ffed', padding: 12, borderRadius: 8, border: '1px solid #b7eb8f' }}>
                  <ThunderboltOutlined style={{ color: '#52c41a', marginRight: 8 }} />
                  {ragResult.answer || t('ai.no_results')}
                </Typography.Paragraph>
                {ragResult.retrieved_docs?.length > 0 && (
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    Retrieved {ragResult.retrieved_docs.length} docs
                  </Typography.Text>
                )}
              </div>
            )}
            {ragResult?.error && <Typography.Text type="danger" style={{ marginTop: 8, display: 'block' }}>{ragResult.error}</Typography.Text>}
          </Card>
        </Col>
      </Row>
    </div>
  )
}
