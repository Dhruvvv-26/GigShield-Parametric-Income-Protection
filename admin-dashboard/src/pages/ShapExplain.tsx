import React, { useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'

interface ShapFeature {
  name: string
  value: number
  color: string
}

const ARJUN: ShapFeature[] = [
  { name: 'City Risk (Delhi NCR)', value: 28.4, color: '#FF5252' },
  { name: 'Coverage Tier (Standard)', value: 18.2, color: '#FF9800' },
  { name: 'Vehicle Risk (Bicycle)', value: 14.7, color: '#FFB74D' },
  { name: 'Seasonality (Monsoon)', value: 12.3, color: '#FFB74D' },
  { name: 'Disruption History (90d)', value: 9.8, color: '#4CAF50' },
  { name: 'Historical AQI Events', value: 7.1, color: '#4CAF50' },
  { name: 'Historical Rain Events', value: 5.9, color: '#4CAF50' },
  { name: 'Work Hours (Full Day)', value: 4.2, color: '#00C9B1' },
  { name: 'Work Days/Month', value: -2.1, color: '#64B5F6' },
  { name: 'Zone Index', value: -1.8, color: '#64B5F6' },
]

const BLR_RIDER: ShapFeature[] = [
  { name: 'City Risk (Bengaluru)', value: -8.6, color: '#64B5F6' },
  { name: 'Coverage Tier (Basic)', value: -6.4, color: '#64B5F6' },
  { name: 'Vehicle Risk (Motorcycle)', value: -5.2, color: '#64B5F6' },
  { name: 'Seasonality (Winter)', value: -3.8, color: '#64B5F6' },
  { name: 'Disruption History (90d)', value: 2.1, color: '#4CAF50' },
  { name: 'Historical AQI Events', value: -1.5, color: '#64B5F6' },
  { name: 'Historical Rain Events', value: 3.2, color: '#4CAF50' },
  { name: 'Work Hours (Peak Only)', value: -2.8, color: '#64B5F6' },
  { name: 'Work Days/Month', value: 1.5, color: '#4CAF50' },
  { name: 'Zone Index', value: -0.8, color: '#64B5F6' },
]

const PROFILES = [
  { id: 'arjun', name: 'Arjun Kumar', city: 'Delhi NCR', vehicle: 'Bicycle', tier: 'Standard', premium: '₹142/week', data: ARJUN },
  { id: 'blr', name: 'Priya Desai', city: 'Bengaluru', vehicle: 'Motorcycle', tier: 'Basic', premium: '₹37/week', data: BLR_RIDER },
]

export default function ShapExplain() {
  const [selectedProfile, setSelectedProfile] = useState(0)
  const profile = PROFILES[selectedProfile]
  const maxAbsVal = Math.max(...profile.data.map(d => Math.abs(d.value)))

  return (
    <div>
      <div className="page-header">
        <h2>SHAP Explainability</h2>
        <p>Feature contribution breakdown for premium pricing — powered by TreeExplainer</p>
      </div>

      <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(2, 1fr)' }}>
        {PROFILES.map((p, i) => (
          <div
            key={p.id}
            className="stat-card"
            style={{
              cursor: 'pointer',
              border: i === selectedProfile ? '2px solid var(--primary)' : '1px solid var(--border)',
              transition: 'all 0.2s',
            }}
            onClick={() => setSelectedProfile(i)}
          >
            <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text)' }}>{p.name}</div>
            <div style={{ color: 'var(--text-dim)', fontSize: 13, marginTop: 4 }}>
              {p.city} • {p.vehicle} • {p.tier}
            </div>
            <div className="stat-value" style={{ marginTop: 8 }}>{p.premium}</div>
          </div>
        ))}
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="card-header">
            <span className="card-title">Feature Contributions (SHAP Values)</span>
          </div>
          <div className="chart-container" style={{ height: 420 }}>
            <ResponsiveContainer>
              <BarChart data={profile.data} layout="vertical" margin={{ left: 160, right: 40 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(30,58,95,0.5)" />
                <XAxis type="number" tick={{ fill: '#8FA3BF', fontSize: 11 }} />
                <YAxis type="category" dataKey="name" tick={{ fill: '#8FA3BF', fontSize: 11 }} width={160} />
                <Tooltip
                  contentStyle={{ background: '#0F2038', border: '1px solid #1E3A5F', borderRadius: 8 }}
                  labelStyle={{ color: '#fff' }}
                  formatter={(value: number) => [`${value > 0 ? '+' : ''}${value.toFixed(1)}`, 'SHAP value']}
                />
                <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                  {profile.data.map((entry, idx) => (
                    <Cell key={idx} fill={entry.color} opacity={0.85} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <span className="card-title">Waterfall Breakdown</span>
          </div>
          <div style={{ padding: '8px 0' }}>
            <div className="shap-bar">
              <span className="shap-label" style={{ fontWeight: 600 }}>Base Rate</span>
              <div className="shap-bar-track">
                <div className="shap-bar-fill" style={{ width: '30%', background: '#5A7090' }} />
              </div>
              <span className="shap-value">₹25.00</span>
            </div>
            {profile.data.map((feat, i) => (
              <div key={i} className="shap-bar">
                <span className="shap-label">{feat.name}</span>
                <div className="shap-bar-track">
                  <div
                    className="shap-bar-fill"
                    style={{
                      width: `${(Math.abs(feat.value) / maxAbsVal) * 80 + 5}%`,
                      background: feat.value > 0
                        ? 'linear-gradient(90deg, #FF5252, #FF9800)'
                        : 'linear-gradient(90deg, #64B5F6, #00C9B1)',
                    }}
                  />
                </div>
                <span className="shap-value" style={{ color: feat.value > 0 ? '#FF9800' : '#64B5F6' }}>
                  {feat.value > 0 ? '+' : ''}{feat.value.toFixed(1)}
                </span>
              </div>
            ))}
            <div className="shap-bar" style={{ borderTop: '1px solid var(--border)', paddingTop: 12, marginTop: 8 }}>
              <span className="shap-label" style={{ fontWeight: 700, color: 'var(--text)' }}>Final Premium</span>
              <div className="shap-bar-track">
                <div className="shap-bar-fill" style={{
                  width: '100%',
                  background: 'linear-gradient(90deg, var(--primary), var(--accent))',
                }} />
              </div>
              <span className="shap-value" style={{ fontWeight: 800, fontSize: 16 }}>{profile.premium}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
