import React, { useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'

interface TriggerEvent {
  id: string
  city: string
  zone: string
  eventType: string
  tier: string
  metricValue: number
  threshold: number
  affectedRiders: number
  totalPayout: number
  status: 'active' | 'resolved'
  startedAt: string
  resolvedAt?: string
}

const MOCK_TRIGGERS: TriggerEvent[] = [
  { id: 'TRG-001', city: 'Delhi NCR', zone: 'delhi_rohini', eventType: 'aqi', tier: 'tier2', metricValue: 420, threshold: 300, affectedRiders: 28, totalPayout: 8400, status: 'active', startedAt: '2026-04-02T06:30:00Z' },
  { id: 'TRG-002', city: 'Delhi NCR', zone: 'delhi_dwarka', eventType: 'aqi', tier: 'tier1', metricValue: 340, threshold: 300, affectedRiders: 15, totalPayout: 2250, status: 'active', startedAt: '2026-04-02T07:15:00Z' },
  { id: 'TRG-003', city: 'Delhi NCR', zone: 'delhi_laxmi_nagar', eventType: 'aqi', tier: 'tier1', metricValue: 310, threshold: 300, affectedRiders: 12, totalPayout: 1800, status: 'active', startedAt: '2026-04-02T07:45:00Z' },
  { id: 'TRG-004', city: 'Mumbai', zone: 'mumbai_powai', eventType: 'heavy_rain', tier: 'tier1', metricValue: 42, threshold: 35, affectedRiders: 18, totalPayout: 3600, status: 'active', startedAt: '2026-04-02T09:00:00Z' },
  { id: 'TRG-005', city: 'Kolkata', zone: 'kolkata_park_street', eventType: 'aqi', tier: 'tier1', metricValue: 305, threshold: 300, affectedRiders: 8, totalPayout: 1200, status: 'resolved', startedAt: '2026-04-01T15:30:00Z', resolvedAt: '2026-04-01T22:00:00Z' },
  { id: 'TRG-006', city: 'Delhi NCR', zone: 'delhi_rohini', eventType: 'aqi', tier: 'tier3', metricValue: 480, threshold: 300, affectedRiders: 32, totalPayout: 16000, status: 'resolved', startedAt: '2026-03-31T05:00:00Z', resolvedAt: '2026-03-31T18:30:00Z' },
  { id: 'TRG-007', city: 'Mumbai', zone: 'mumbai_andheri', eventType: 'heavy_rain', tier: 'tier2', metricValue: 68, threshold: 35, affectedRiders: 24, totalPayout: 7200, status: 'resolved', startedAt: '2026-03-30T12:00:00Z', resolvedAt: '2026-03-30T20:00:00Z' },
  { id: 'TRG-008', city: 'Hyderabad', zone: 'hyderabad_gachibowli', eventType: 'extreme_heat', tier: 'tier1', metricValue: 44.2, threshold: 43, affectedRiders: 10, totalPayout: 1500, status: 'resolved', startedAt: '2026-03-29T10:00:00Z', resolvedAt: '2026-03-29T17:30:00Z' },
]

const DAILY_TRIGGERS = [
  { day: 'Mar 28', aqi: 0, rain: 0, heat: 1, wind: 0 },
  { day: 'Mar 29', aqi: 0, rain: 0, heat: 1, wind: 0 },
  { day: 'Mar 30', aqi: 0, rain: 2, heat: 0, wind: 0 },
  { day: 'Mar 31', aqi: 3, rain: 0, heat: 0, wind: 0 },
  { day: 'Apr 1', aqi: 1, rain: 0, heat: 0, wind: 0 },
  { day: 'Apr 2', aqi: 3, rain: 1, heat: 0, wind: 0 },
]

export default function TriggerHistory() {
  const [filter, setFilter] = useState<'all' | 'active' | 'resolved'>('all')
  
  const filtered = filter === 'all' ? MOCK_TRIGGERS : MOCK_TRIGGERS.filter(t => t.status === filter)
  const activeCount = MOCK_TRIGGERS.filter(t => t.status === 'active').length
  const totalPayouts = MOCK_TRIGGERS.reduce((s, t) => s + t.totalPayout, 0)
  const totalRiders = MOCK_TRIGGERS.reduce((s, t) => s + t.affectedRiders, 0)

  return (
    <div>
      <div className="page-header">
        <h2>Trigger History</h2>
        <p>All parametric trigger events across covered zones</p>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-value" style={{ color: activeCount > 0 ? '#FF9800' : undefined }}>{activeCount}</div>
          <div className="stat-label">Active Now</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{MOCK_TRIGGERS.length}</div>
          <div className="stat-label">Total Events (7d)</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">₹{(totalPayouts / 1000).toFixed(1)}K</div>
          <div className="stat-label">Total Payouts</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{totalRiders}</div>
          <div className="stat-label">Riders Paid</div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <span className="card-title">Triggers by Type (Last 7 Days)</span>
        </div>
        <div className="chart-container" style={{ height: 280 }}>
          <ResponsiveContainer>
            <BarChart data={DAILY_TRIGGERS}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(30,58,95,0.5)" />
              <XAxis dataKey="day" tick={{ fill: '#8FA3BF', fontSize: 12 }} />
              <YAxis tick={{ fill: '#8FA3BF', fontSize: 11 }} />
              <Tooltip contentStyle={{ background: '#0F2038', border: '1px solid #1E3A5F', borderRadius: 8 }} />
              <Legend />
              <Bar dataKey="aqi" name="AQI" fill="#FF9800" radius={[4, 4, 0, 0]} />
              <Bar dataKey="rain" name="Heavy Rain" fill="#64B5F6" radius={[4, 4, 0, 0]} />
              <Bar dataKey="heat" name="Extreme Heat" fill="#FF5252" radius={[4, 4, 0, 0]} />
              <Bar dataKey="wind" name="Cyclone Wind" fill="#9C27B0" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <span className="card-title">Trigger Events</span>
          <div style={{ display: 'flex', gap: 8 }}>
            {(['all', 'active', 'resolved'] as const).map(f => (
              <button
                key={f}
                className="btn"
                style={{
                  background: filter === f ? 'var(--primary)' : 'var(--surface-light)',
                  color: filter === f ? 'var(--bg)' : 'var(--text-dim)',
                }}
                onClick={() => setFilter(f)}
              >
                {f.charAt(0).toUpperCase() + f.slice(1)}
              </button>
            ))}
          </div>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>City / Zone</th>
              <th>Type</th>
              <th>Tier</th>
              <th>Value</th>
              <th>Riders</th>
              <th>Payout</th>
              <th>Status</th>
              <th>Started</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(t => (
              <tr key={t.id}>
                <td style={{ fontFamily: 'monospace', fontSize: 13 }}>{t.id}</td>
                <td>
                  <div>{t.city}</div>
                  <div style={{ color: 'var(--text-muted)', fontSize: 11 }}>{t.zone.replace(/_/g, ' ')}</div>
                </td>
                <td>{t.eventType.replace(/_/g, ' ')}</td>
                <td><span className={`badge badge-${t.tier}`}>{t.tier.toUpperCase()}</span></td>
                <td>
                  <span style={{ fontWeight: 600 }}>{t.metricValue}</span>
                  <span style={{ color: 'var(--text-muted)', fontSize: 11 }}> / {t.threshold}</span>
                </td>
                <td>{t.affectedRiders}</td>
                <td style={{ fontWeight: 600 }}>₹{t.totalPayout.toLocaleString()}</td>
                <td>
                  <span style={{
                    display: 'inline-flex', alignItems: 'center', gap: 6,
                    color: t.status === 'active' ? '#FF9800' : '#00E676',
                    fontWeight: 600, fontSize: 13,
                  }}>
                    {t.status === 'active' && <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#FF9800', animation: 'pulse 2s infinite', display: 'inline-block' }} />}
                    {t.status}
                  </span>
                </td>
                <td style={{ fontSize: 12, color: 'var(--text-dim)' }}>
                  {new Date(t.startedAt).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
                  {' '}
                  {new Date(t.startedAt).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
