const BASE = '/api/stats'

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export const api = {
  dashboard: ()     => fetchJSON<any>(`${BASE}/dashboard`),
  salesTrend: ()    => fetchJSON<any>(`${BASE}/sales-trend`),
  hourlyHeatmap: () => fetchJSON<any>(`${BASE}/hourly-heatmap`),
  userSegments: ()  => fetchJSON<any>(`${BASE}/user-segments`),
  topUsers: ()      => fetchJSON<any>(`${BASE}/top-users`),
  productRank: ()   => fetchJSON<any>(`${BASE}/product-rank`),
  categoryShare: () => fetchJSON<any>(`${BASE}/category-share`),
  funnel: ()        => fetchJSON<any>(`${BASE}/funnel`),
  services: ()      => fetchJSON<any>(`${BASE}/services`),
  query: (sql: string) =>
    fetch(`${BASE}/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sql }),
    }).then(r => r.json()),
}
