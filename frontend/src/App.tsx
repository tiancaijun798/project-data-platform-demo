import { Routes, Route, Navigate } from 'react-router-dom'
import MainLayout from './layouts/MainLayout'
import Dashboard from './pages/Dashboard'
import Users from './pages/Users'
import Products from './pages/Products'
import Funnel from './pages/Funnel'
import Monitor from './pages/Monitor'
import Query from './pages/Query'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<MainLayout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="users" element={<Users />} />
        <Route path="products" element={<Products />} />
        <Route path="funnel" element={<Funnel />} />
        <Route path="monitor" element={<Monitor />} />
        <Route path="query" element={<Query />} />
      </Route>
    </Routes>
  )
}
