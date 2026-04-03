import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import ZoneMap from './pages/ZoneMap'
import FraudQueue from './pages/FraudQueue'
import ShapExplain from './pages/ShapExplain'
import LossRatio from './pages/LossRatio'
import TriggerHistory from './pages/TriggerHistory'
import './index.css'

function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <nav className="sidebar">
          <div className="logo">
            <span className="logo-icon">🛡️</span>
            <h1>GigShield</h1>
            <span className="logo-sub">Admin</span>
          </div>
          <div className="nav-links">
            <NavLink to="/" end className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              <span className="nav-icon">🗺️</span> Live Zones
            </NavLink>
            <NavLink to="/fraud" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              <span className="nav-icon">🔍</span> Fraud Queue
            </NavLink>
            <NavLink to="/shap" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              <span className="nav-icon">📊</span> SHAP Explainer
            </NavLink>
            <NavLink to="/loss" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              <span className="nav-icon">💰</span> Loss Ratio
            </NavLink>
            <NavLink to="/triggers" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              <span className="nav-icon">⚡</span> Trigger History
            </NavLink>
          </div>
          <div className="nav-footer">
            <div className="status-indicator">
              <span className="status-dot"></span>
              All services healthy
            </div>
          </div>
        </nav>
        <main className="main-content">
          <Routes>
            <Route path="/" element={<ZoneMap />} />
            <Route path="/fraud" element={<FraudQueue />} />
            <Route path="/shap" element={<ShapExplain />} />
            <Route path="/loss" element={<LossRatio />} />
            <Route path="/triggers" element={<TriggerHistory />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
