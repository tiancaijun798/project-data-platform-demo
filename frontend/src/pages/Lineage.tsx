import { Card, Typography } from 'antd'
import { useI18n } from '../i18n'

export default function Lineage() {
  const { t } = useI18n()
  return (
    <div>
      <Typography.Title level={3}>{t('lineage.title')}</Typography.Title>
      <Card>
        <iframe
          src="/api/../lineage.html"
          width="100%"
          height="700"
          style={{ border: 0, borderRadius: 8 }}
          title="Data Lineage"
        />
        <Typography.Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
          Full pipeline: Kafka → PySpark → dbt → PostgreSQL → FastAPI → React
        </Typography.Text>
      </Card>
    </div>
  )
}
