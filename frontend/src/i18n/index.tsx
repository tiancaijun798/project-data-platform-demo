import React, { createContext, useContext, useState, useCallback } from 'react'

type Lang = 'zh' | 'en'

interface I18nContextType {
  lang: Lang
  toggle: () => void
  t: (key: string) => string
}

const I18nContext = createContext<I18nContextType>({ lang: 'zh', toggle: () => {}, t: (k) => k })

const messages: Record<Lang, Record<string, string>> = {
  zh: {
    'app.title': 'Data Platform Demo — 电商数据洞察平台',
    'menu.dashboard': '销售大盘',
    'menu.users': '用户分析',
    'menu.products': '商品分析',
    'menu.funnel': '转化漏斗',
    'menu.ai_lab': 'AI 实验室',
    'menu.graph': '知识图谱',
    'menu.lineage': '数据血缘',
    'menu.mlflow': 'ML 实验',
    'menu.monitor': '实时监控',
    'menu.query': '数据查询',
    'dashboard.title': '销售大盘',
    'dashboard.total_events': '事件总数',
    'dashboard.total_orders': '订单总数',
    'dashboard.active_users': '活跃用户',
    'dashboard.conversion_rate': '转化率',
    'dashboard.data_scale': '数据规模',
    'dashboard.trend': '近 7 天趋势',
    'dashboard.heatmap': '时段热力图',
    'ai.title': 'AI 实验室',
    'ai.vector_search': '向量语义搜索',
    'ai.rag_qa': 'RAG 智能问答',
    'ai.search_placeholder': '输入自然语言查询，例如：移动端用户购买行为',
    'ai.ask_placeholder': '输入你的问题，例如：哪些用户通过移动端完成了购买？',
    'ai.search_btn': '搜索',
    'ai.ask_btn': '提问',
    'ai.no_results': '暂无结果',
    'ai.elapsed': '耗时',
    'ai.score': '相似度',
    'graph.title': '知识图谱',
    'graph.stats': '图统计',
    'graph.user_path': '用户行为路径',
    'graph.path_placeholder': '输入用户 ID，例如 U0001',
    'lineage.title': '数据血缘',
    'mlflow.title': 'ML 实验跟踪',
    'monitor.title': '实时监控',
    'monitor.services': '服务清单',
    'monitor.grafana': 'Grafana 监控大屏',
    'query.title': '数据查询',
    'query.placeholder': '输入 SQL 查询语句...',
    'query.run': '执行',
    'query.only_select': '仅允许 SELECT 查询',
    'users.title': '用户分析',
    'users.segments': '用户分群',
    'users.top_users': '活跃用户排行榜',
    'products.title': '商品分析',
    'funnel.title': '转化漏斗',
    'lang.switch': 'English',
  },
  en: {
    'app.title': 'Data Platform Demo — E-Commerce Insights',
    'menu.dashboard': 'Dashboard',
    'menu.users': 'Users',
    'menu.products': 'Products',
    'menu.funnel': 'Funnel',
    'menu.ai_lab': 'AI Lab',
    'menu.graph': 'Graph',
    'menu.lineage': 'Lineage',
    'menu.mlflow': 'ML Experiments',
    'menu.monitor': 'Monitor',
    'menu.query': 'SQL Query',
    'dashboard.title': 'Dashboard',
    'dashboard.total_events': 'Total Events',
    'dashboard.total_orders': 'Orders',
    'dashboard.active_users': 'Active Users',
    'dashboard.conversion_rate': 'Conversion Rate',
    'dashboard.data_scale': 'Data Scale',
    'dashboard.trend': '7-Day Trend',
    'dashboard.heatmap': 'Hourly Heatmap',
    'ai.title': 'AI Lab',
    'ai.vector_search': 'Vector Semantic Search',
    'ai.rag_qa': 'RAG Q&A',
    'ai.search_placeholder': 'Natural language query, e.g. mobile purchase behavior',
    'ai.ask_placeholder': 'Ask a question, e.g. Which users purchased via mobile?',
    'ai.search_btn': 'Search',
    'ai.ask_btn': 'Ask',
    'ai.no_results': 'No results',
    'ai.elapsed': 'Latency',
    'ai.score': 'Score',
    'graph.title': 'Knowledge Graph',
    'graph.stats': 'Graph Statistics',
    'graph.user_path': 'User Behavior Path',
    'graph.path_placeholder': 'Enter user ID, e.g. U0001',
    'lineage.title': 'Data Lineage',
    'mlflow.title': 'ML Experiments',
    'monitor.title': 'Service Monitor',
    'monitor.services': 'Service List',
    'monitor.grafana': 'Grafana Dashboard',
    'query.title': 'SQL Query',
    'query.placeholder': 'Enter SQL query...',
    'query.run': 'Run',
    'query.only_select': 'Only SELECT queries allowed',
    'users.title': 'User Analysis',
    'users.segments': 'User Segments',
    'users.top_users': 'Top Active Users',
    'products.title': 'Product Analysis',
    'funnel.title': 'Conversion Funnel',
    'lang.switch': '中文',
  },
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLang] = useState<Lang>('zh')
  const toggle = useCallback(() => setLang((l) => (l === 'zh' ? 'en' : 'zh')), [])
  const t = useCallback((key: string) => messages[lang][key] || key, [lang])
  return <I18nContext.Provider value={{ lang, toggle, t }}>{children}</I18nContext.Provider>
}

export function useI18n() {
  return useContext(I18nContext)
}

export default I18nContext
