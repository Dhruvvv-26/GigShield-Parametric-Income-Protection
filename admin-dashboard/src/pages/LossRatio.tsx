import React from 'react'
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, Legend, PieChart, Pie, Cell
} from 'recharts'

const MONTHLY_DATA = [
  { month: 'Oct', premiums: 42500, payouts: 18200, lossRatio: 42.8 },
  { month: 'Nov', premiums: 45800, payouts: 28400, lossRatio: 62.0 },
  { month: 'Dec', premiums: 47200, payouts: 15800, lossRatio: 33.5 },
  { month: 'Jan', premiums: 48900, payouts: 22100, lossRatio: 45.2 },
  { month: 'Feb', premiums: 46300, payouts: 12400, lossRatio: 26.8 },
  { month: 'Mar', premiums: 51200, payouts: 31800, lossRatio: 62.1 },
  { month: 'Apr', premiums: 53400, payouts: 24600, lossRatio: 46.1 },
]

const CITY_BREAKDOWN = [
  { city: 'Delhi NCR', premiums: 68200, payouts: 38400, lossRatio: 56.3, riders: 312 },
  { city: 'Mumbai', premiums: 54800, payouts: 31200, lossRatio: 56.9, riders: 228 },
  { city: 'Kolkata', premiums: 35400, payouts: 18600, lossRatio: 52.5, riders: 124 },
  { city: 'Hyderabad', premiums: 28600, payouts: 12800, lossRatio: 44.8, riders: 87 },
  { city: 'Pune', premiums: 22400, payouts: 8400, lossRatio: 37.5, riders: 54 },
  { city: 'Bengaluru', premiums: 18900, payouts: 5200, lossRatio: 27.5, riders: 42 },
]

const TIER_DIST = [
  { name: 'Basic', value: 45, color: '#4CAF50' },
  { name: 'Standard', value: 35, color: '#FF9800' },
  { name: 'Premium', value: 20, color: '#FF5252' },
]

export default function LossRatio() {
  const totalPremiums = MONTHLY_DATA.reduce((s, d) => s + d.premiums, 0)
  const totalPayouts = MONTHLY_DATA.reduce((s, d) => s + d.payouts, 0)
  const avgLoss = ((totalPayouts / totalPremiums) * 100).toFixed(1)

  return (
    <div>
      <div className="page-header">
        <h2>Loss Ratio Analytics</h2>
        <p>Premium collection vs payout disbursements — actuarial performance</p>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-value">₹{(totalPremiums / 1000).toFixed(0)}K</div>
          <div className="stat-label">Total Premiums</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: '#FF9800' }}>₹{(totalPayouts / 1000).toFixed(0)}K</div>
          <div className="stat-label">Total Payouts</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: parseFloat(avgLoss) > 60 ? '#FF5252' : '#00E676' }}>{avgLoss}%</div>
          <div className="stat-label">Avg Loss Ratio</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">847</div>
          <div className="stat-label">Active Policies</div>
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="card-header">
            <span className="card-title">Premium vs Payouts (Monthly)</span>
          </div>
          <div className="chart-container">
            <ResponsiveContainer>
              <AreaChart data={MONTHLY_DATA}>
                <defs>
                  <linearGradient id="premGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#00C9B1" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#00C9B1" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="payGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#FF9800" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#FF9800" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(30,58,95,0.5)" />
                <XAxis dataKey="month" tick={{ fill: '#8FA3BF', fontSize: 12 }} />
                <YAxis tick={{ fill: '#8FA3BF', fontSize: 11 }} tickFormatter={v => `₹${v / 1000}K`} />
                <Tooltip
                  contentStyle={{ background: '#0F2038', border: '1px solid #1E3A5F', borderRadius: 8 }}
                  labelStyle={{ color: '#fff' }}
                  formatter={(v: number) => [`₹${v.toLocaleString()}`, '']}
                />
                <Legend />
                <Area type="monotone" dataKey="premiums" name="Premiums" stroke="#00C9B1" fill="url(#premGradient)" strokeWidth={2} />
                <Area type="monotone" dataKey="payouts" name="Payouts" stroke="#FF9800" fill="url(#payGradient)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <span className="card-title">Loss Ratio Trend</span>
          </div>
          <div className="chart-container">
            <ResponsiveContainer>
              <LineChart data={MONTHLY_DATA}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(30,58,95,0.5)" />
                <XAxis dataKey="month" tick={{ fill: '#8FA3BF', fontSize: 12 }} />
                <YAxis tick={{ fill: '#8FA3BF', fontSize: 11 }} domain={[0, 100]} tickFormatter={v => `${v}%`} />
                <Tooltip
                  contentStyle={{ background: '#0F2038', border: '1px solid #1E3A5F', borderRadius: 8 }}
                  labelStyle={{ color: '#fff' }}
                  formatter={(v: number) => [`${v.toFixed(1)}%`, 'Loss Ratio']}
                />
                <Line type="monotone" dataKey="lossRatio" stroke="#FF5252" strokeWidth={3} dot={{ r: 5, fill: '#FF5252' }} />
                {/* Target line at 55% */}
                <Line type="monotone" dataKey={() => 55} stroke="#5A7090" strokeDasharray="5 5" name="Target (55%)" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="grid-2" style={{ marginTop: 0 }}>
        <div className="card">
          <div className="card-header">
            <span className="card-title">Loss Ratio by City</span>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>City</th>
                <th>Riders</th>
                <th>Premiums</th>
                <th>Payouts</th>
                <th>Loss Ratio</th>
              </tr>
            </thead>
            <tbody>
              {CITY_BREAKDOWN.map(city => (
                <tr key={city.city}>
                  <td style={{ fontWeight: 600 }}>{city.city}</td>
                  <td>{city.riders}</td>
                  <td>₹{(city.premiums / 1000).toFixed(1)}K</td>
                  <td>₹{(city.payouts / 1000).toFixed(1)}K</td>
                  <td>
                    <span style={{
                      color: city.lossRatio > 55 ? '#FF9800' : '#00E676',
                      fontWeight: 700,
                    }}>
                      {city.lossRatio.toFixed(1)}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card">
          <div className="card-header">
            <span className="card-title">Coverage Tier Distribution</span>
          </div>
          <div className="chart-container" style={{ height: 260 }}>
            <ResponsiveContainer>
              <PieChart>
                <Pie data={TIER_DIST} cx="50%" cy="50%" innerRadius={60} outerRadius={100} paddingAngle={5} dataKey="value">
                  {TIER_DIST.map((entry, idx) => (
                    <Cell key={idx} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: '#0F2038', border: '1px solid #1E3A5F', borderRadius: 8 }}
                  formatter={(v: number) => [`${v}%`, '']}
                />
                <Legend
                  formatter={(value) => <span style={{ color: '#8FA3BF', fontSize: 13 }}>{value}</span>}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  )
}
