import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import React, { useEffect, useState } from 'react'
import { fetchPaymentSummary, fetchTriggerStatus } from './lib/api'
import type { PaymentSummary, TriggerStatus } from './lib/types'

import FraudQueue from './components/FraudQueue'
import SHAPWaterfall from './components/SHAPWaterfall'
import ZoneHeatmap from './components/ZoneHeatmap'
import DualSelfieCheck from './components/DualSelfieCheck'
import LiveMetrics from './components/LiveMetrics'
import ActuarialDashboard from './components/ActuarialDashboard'

function Topbar({ live, triggerStatus }: { live: boolean; triggerStatus: TriggerStatus | null }) {
  const [now, setNow] = useState(new Date())
  useEffect(() => { const t = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(t) }, [])

  return (
    <div className="topbar">
      <div className="topbar-logo">
        ⚡ KavachAI
        <span>Admin Command Center — Phase 3</span>
      </div>
      {triggerStatus?.active_triggers?.length ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--amber)' }}>
          <span style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--amber)', display: 'inline-block', animation: 'pulse-dot 1s ease-in-out infinite' }} />
          {triggerStatus.active_triggers.length} active trigger{triggerStatus.active_triggers.length > 1 ? 's' : ''} live
        </div>
      ) : null}
      <div className="topbar-right">
        <span className="topbar-tag">{now.toLocaleTimeString('en-IN', { hour12: false })}</span>
        <div className="live-dot" style={{ background: live ? 'var(--teal)' : 'var(--amber)' }} />
        <span className="topbar-tag" style={{ color: live ? 'var(--teal)' : 'var(--amber)' }}>
          {live ? 'LIVE' : 'DEMO'}
        </span>
        <span style={{
          fontSize: 9,
          padding: '2px 6px',
          borderRadius: 4,
          background: 'rgba(123, 97, 255, 0.15)',
          color: '#7b61ff',
          border: '1px solid rgba(123, 97, 255, 0.3)',
          marginLeft: 4,
        }}>
          v3.0
        </span>
      </div>
    </div>
  )
}

function Sidebar({ softHolds, pendingClaims }: { softHolds: number; pendingClaims: number }) {
  return (
    <nav className="sidebar">
      <div className="nav-section">Overview</div>
      <NavLink to="/" end className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
        <span className="nav-icon">◈</span> Live Metrics
      </NavLink>

      <div className="nav-section">Fraud Management</div>
      <NavLink to="/fraud-queue" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
        <span className="nav-icon">⚠</span> Fraud Queue
        {pendingClaims > 0 && <span className="nav-badge">{pendingClaims}</span>}
      </NavLink>
      <NavLink to="/dual-selfie" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
        <span className="nav-icon">◉</span> Dual Selfie Check
        {softHolds > 0 && <span className="nav-badge amber">{softHolds}</span>}
      </NavLink>

      <div className="nav-section">Analytics</div>
      <NavLink to="/shap" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
        <span className="nav-icon">≋</span> SHAP Explainer
      </NavLink>
      <NavLink to="/zones" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
        <span className="nav-icon">◎</span> Zone Heatmap
      </NavLink>
      <NavLink to="/actuarial" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
        <span className="nav-icon">₹</span> Actuarial / BCR
      </NavLink>

      <div style={{ marginTop: 'auto', padding: '16px', borderTop: '1px solid var(--border)' }}>
        <div style={{ fontSize: 11, color: 'var(--text-3)', marginBottom: 4 }}>Demo anchor</div>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--teal)', wordBreak: 'break-all' }}>
          Arjun Kumar<br />delhi_rohini
        </div>
      </div>
    </nav>
  )
}


class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: string }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props)
    this.state = { hasError: false, error: '' }
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error: error.message }
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          height: '60vh', color: 'var(--text-3)', textAlign: 'center',
        }}>
          <div>
            <div style={{ fontSize: 48, marginBottom: 16 }}>⚡</div>
            <h2 style={{ fontSize: 18, color: 'var(--text-1)', marginBottom: 8 }}>Something went wrong</h2>
            <p style={{ fontSize: 13, maxWidth: 400, margin: '0 auto' }}>{this.state.error}</p>
            <button
              onClick={() => { this.setState({ hasError: false, error: '' }); window.location.reload() }}
              style={{
                marginTop: 16, padding: '8px 24px', borderRadius: 8,
                background: 'var(--teal)', color: '#000', border: 'none',
                cursor: 'pointer', fontWeight: 600,
              }}
            >
              Reload
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

export default function App() {
  const [summary, setSummary] = useState<PaymentSummary | null>(null)
  const [triggerStatus, setTriggerStatus] = useState<TriggerStatus | null>(null)
  const [live, setLive] = useState(false)

  useEffect(() => {
    async function load() {
      const [s, t] = await Promise.all([fetchPaymentSummary(), fetchTriggerStatus()])
      setSummary(s.data)
      setTriggerStatus(t.data)
      setLive(s.live || t.live)
    }
    load()
    const interval = setInterval(load, 15000)
    return () => clearInterval(interval)
  }, [])

  const softHolds = (summary as any)?.soft_holds_24h ?? 0
  const pendingClaims = summary?.claims_pending ?? 0

  return (
    <div className="shell">
      <Topbar live={live} triggerStatus={triggerStatus} />
      <Sidebar softHolds={softHolds} pendingClaims={pendingClaims} />
      <main className="main">
        <Routes>
          <Route path="/" element={<LiveMetrics summary={summary} triggerStatus={triggerStatus} live={live} />} />
          <Route path="/fraud-queue" element={<FraudQueue live={live} />} />
          <Route path="/dual-selfie" element={<DualSelfieCheck live={live} />} />
          <Route path="/shap" element={<SHAPWaterfall live={live} />} />
          <Route path="/zones" element={<ZoneHeatmap live={live} />} />
          <Route path="/actuarial" element={<ActuarialDashboard live={live} />} />
        </Routes>
      </main>
    </div>
  )
}
