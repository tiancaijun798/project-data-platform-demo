// ---- 数据统计类型 ----
export interface DashboardStats {
  today_sales: number
  today_orders: number
  today_users: number
  total_events: number
  conversion_rate: number
}

export interface SalesTrend {
  date: string
  sales: number
  orders: number
}

export interface HourlyHeatmap {
  hour: number
  events: number
}

export interface UserSegment {
  segment: string
  users: number
  events: number
  pct: number
}

export interface TopUser {
  user_id: string
  segment: string
  total_events: number
  first_seen: string
  last_seen: string
}

export interface ProductRank {
  product_id: string
  category: string
  total_views: number
  total_purchases: number
  conversion_rate: number
}

export interface CategoryShare {
  category: string
  views: number
  purchases: number
  pct: number
}

export interface FunnelStep {
  name: string
  value: number
  pct: number
}

export interface ServiceStatus {
  name: string
  status: 'running' | 'stopped' | 'unknown'
  port: number
  url: string
}

export interface QueryResult {
  columns: string[]
  rows: Record<string, unknown>[]
  row_count: number
  elapsed_ms: number
}
