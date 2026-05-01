import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import MatchDetailPage from './pages/MatchDetailPage'
import BacktestPage from './pages/BacktestPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="match/:id" element={<MatchDetailPage />} />
        <Route path="backtests" element={<BacktestPage />} />
      </Route>
    </Routes>
  )
}
