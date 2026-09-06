const BASE = '/api'

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

async function postJSON<T>(url: string, body: any): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export const aiApi = {
  dataOverview: ()        => fetchJSON<any>(`${BASE}/stats/data-overview`),
  vectorSearch: (q: string, k = 5) =>
    fetchJSON<any>(`${BASE}/ai/vector-search?q=${encodeURIComponent(q)}&k=${k}`),
  ragQuery: (query: string, top_k = 5) =>
    postJSON<any>(`${BASE}/ai/rag-query`, { query, top_k }),
  graphStats: ()          => fetchJSON<any>(`${BASE}/ai/graph-stats`),
  graphPath: (userId: string) =>
    fetchJSON<any>(`${BASE}/ai/graph-path?user_id=${encodeURIComponent(userId)}&limit=10`),
  mlflowExperiments: ()   => fetchJSON<any>(`${BASE}/ai/mlflow-experiments`),
}
