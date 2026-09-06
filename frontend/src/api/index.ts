import type { StatsResponse, TableResponse } from '../types'

const BASE = '/api/stats'

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export const api = {
  dashboard: ()     => fetchJSON<StatsResponse>(`${BASE}/dashboard`),
  salesTrend: ()    => fetchJSON<TableResponse>(`${BASE}/sales-trend`),
  hourlyHeatmap: () => fetchJSON<TableResponse>(`${BASE}/hourly-heatmap`),
  userSegments: ()  => fetchJSON<TableResponse>(`${BASE}/user-segments`),
  topUsers: ()      => fetchJSON<TableResponse>(`${BASE}/top-users`),
  productRank: ()   => fetchJSON<TableResponse>(`${BASE}/product-rank`),
  categoryShare: () => fetchJSON<TableResponse>(`${BASE}/category-share`),
  funnel: ()        => fetchJSON<TableResponse>(`${BASE}/funnel`),
  services: ()      => fetchJSON<TableResponse>(`${BASE}/services`),
  dataOverview: ()  => fetchJSON<any>(`${BASE}/data-overview`),
  query: (sql: string) =>
    fetch(`${BASE}/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sql }),
    }).then(r => r.json()),
}
