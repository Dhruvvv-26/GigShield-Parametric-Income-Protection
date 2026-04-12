import { useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, Cell, ResponsiveContainer, ReferenceLine } from 'recharts'
import type { SHAPInput } from '../lib/types'
import { calculatePremium } from '../lib/api'

const FEATURE_LABELS: Record<string, string> = {
  base_rate: 'Base rate',
  zone_aqi_risk: 'Zone AQI risk',
  seasonality_month: 'Month seasonality',
  vehicle_type_bicycle: 'Vehicle type (bicycle)',
  disruption_history_90d: 'Disruption history 90d',
  declared_daily_trips: 'Daily trip volume',
  avg_daily_earnings: 'Daily earnings baseline',
  historical_rain_events: 'Rain event history',
  platform_blinkit_multiplier: 'Platform (Blinkit)',
  coverage_tier_standard: 'Coverage tier (Standard)',
  monthly_work_days: 'Monthly work days',
  new_rider_discount: 'New rider discount',
  zone_clustering_adjustment: 'Zone cluster adjustment',
}

interface WaterfallPoint {
  name: string
  contribution: number
  cumulative: number
  positive: boolean
  isTotal: boolean
}

function buildWaterfall(shap: Record<string, number>): WaterfallPoint[] {
  const sorted = Object.entries(shap).sort(([, a], [, b]) => Math.abs(b) - Math.abs(a))
  let running = 0
  const points: WaterfallPoint[] = []

  for (const [key, val] of sorted) {
    const prev = running
    running += val
    points.push({
      name: FEATURE_LABELS[key] ?? key,
      contribution: val,
      cumulative: val >= 0 ? prev : running,
      positive: val >= 0,
      isTotal: false,
    })
  }

  points.push({
    name: 'Total Premium',
    contribution: running,
    cumulative: 0,
    positive: true,
    isTotal: true,
  })

  return points
}

const CustomTooltip = ({ active, payload }: any) => {
  if (!active || !payload?.length) return null
  const d = payload[0]?.payload as WaterfallPoint
  if (!d) return null
  return (
    <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-2)', borderRadius: 8, padding: '10px 14px', fontSize: 12 }}>
      <div style={{ color: 'var(--text-2)', marginBottom: 4 }}>{d.name}</div>
      <div style={{ color: d.positive ? 'var(--teal)' : 'var(--red)', fontFamily: 'IBM Plex Mono', fontWeight: 600, fontSize: 14 }}>
        {d.isTotal ? '=' : (d.positive ? '+' : '')}₹{d.contribution.toFixed(2)}
      </div>
    </div>
  )
}

export default function SHAPWaterfall({ live }: { live: boolean }) {
  const [inputs, setInputs] = useState<SHAPInput>({
    city: 'delhi_ncr',
    vehicle_type: 'bicycle',
    coverage_tier: 'standard',
    month: 7,
    historical_aqi_events_12m: 45,
    historical_rain_events_12m: 28,
    disruption_history_90d: 15,
    declared_daily_trips: 30,
    avg_daily_earnings: 1100.0,
    monthly_work_days: 22,
  })
  const [result, setResult] = useState<{ premium: number; shap: Record<string, number> } | null>(null)
  const [loading, setLoading] = useState(false)
  const [fromLive, setFromLive] = useState(false)

  async function handleCalculate() {
    setLoading(true)
    const { data, live: isLive } = await calculatePremium(inputs)
    setResult({ premium: data.recommended_premium, shap: data.shap_breakdown })
    setFromLive(isLive)
    setLoading(false)
  }

  const waterfallData = result ? buildWaterfall(result.shap) : null

  function set<K extends keyof SHAPInput>(k: K, v: SHAPInput[K]) {
    setInputs(prev => ({ ...prev, [k]: v }))
  }

  return (
    <>
      <div className="page-header">
        <div className="page-title">SHAP Premium Explainer</div>
        <div className="page-sub">XGBoost + LightGBM ensemble — per-feature premium contribution (IRDAI-compliant explainability)</div>
      </div>

      {!live && (
        <div className="demo-banner">
          ⚡ Demo mode — ML Service offline. Showing illustrative SHAP breakdown. Start docker-compose for live model inference.
        </div>
      )}

      <div className="card">
        <div className="card-header">
          <div className="card-title">Rider Profile Inputs</div>
          {result && (
            <span className="badge badge-teal">
              {fromLive ? '● Live model' : '● Demo SHAP'}
            </span>
          )}
        </div>
        <div className="shap-input-row">
          <div className="shap-input-group">
            <label>City</label>
            <select value={inputs.city} onChange={e => set('city', e.target.value)}>
              <option value="delhi_ncr">Delhi NCR</option>
              <option value="mumbai">Mumbai</option>
              <option value="bengaluru">Bengaluru</option>
              <option value="hyderabad">Hyderabad</option>
              <option value="pune">Pune</option>
            </select>
          </div>
          <div className="shap-input-group">
            <label>Vehicle</label>
            <select value={inputs.vehicle_type} onChange={e => set('vehicle_type', e.target.value)}>
              <option value="bicycle">Bicycle</option>
              <option value="ebike">E-Bike</option>
              <option value="motorcycle">Motorcycle</option>
            </select>
          </div>
          <div className="shap-input-group">
            <label>Coverage Tier</label>
            <select value={inputs.coverage_tier} onChange={e => set('coverage_tier', e.target.value)}>
              <option value="basic">Basic</option>
              <option value="standard">Standard</option>
              <option value="premium">Premium</option>
            </select>
          </div>
          <div className="shap-input-group">
            <label>Month</label>
            <select value={inputs.month} onChange={e => set('month', Number(e.target.value))}>
              {Array.from({ length: 12 }, (_, i) => (
                <option key={i + 1} value={i + 1}>
                  {new Date(2026, i, 1).toLocaleString('default', { month: 'long' })}
                </option>
              ))}
            </select>
          </div>
          <div className="shap-input-group">
            <label>AQI events (12m)</label>
            <input type="number" min={0} max={365} value={inputs.historical_aqi_events_12m}
              onChange={e => set('historical_aqi_events_12m', Number(e.target.value))} style={{ width: 80 }} />
          </div>
          <div className="shap-input-group">
            <label>Rain events (12m)</label>
            <input type="number" min={0} max={365} value={inputs.historical_rain_events_12m}
              onChange={e => set('historical_rain_events_12m', Number(e.target.value))} style={{ width: 80 }} />
          </div>
          <div className="shap-input-group">
            <label>Daily trips</label>
            <input type="number" min={1} max={60} value={inputs.declared_daily_trips}
              onChange={e => set('declared_daily_trips', Number(e.target.value))} style={{ width: 70 }} />
          </div>
          <div className="shap-input-group">
            <label>Avg daily earnings</label>
            <input type="number" min={100} max={5000} value={inputs.avg_daily_earnings}
              onChange={e => set('avg_daily_earnings', Number(e.target.value))} style={{ width: 90 }} />
          </div>
          <button className="btn btn-teal" onClick={handleCalculate} disabled={loading} style={{ height: 36, alignSelf: 'flex-end' }}>
            {loading ? 'Calculating…' : '⚡ Calculate Premium'}
          </button>
        </div>

        {result && waterfallData && (
          <>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, margin: '16px 0 4px' }}>
              <div style={{ fontSize: 13, color: 'var(--text-2)' }}>Recommended weekly premium</div>
              <div style={{ fontSize: 36, fontWeight: 700, color: 'var(--teal)', fontFamily: 'IBM Plex Mono' }}>
                ₹{result.premium.toFixed(2)}
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-3)' }}>/ week · {inputs.coverage_tier} tier</div>
            </div>

            <div style={{ fontSize: 12, color: 'var(--text-3)', marginBottom: 16 }}>
              Feature contributions — positive values increase premium risk, negative values represent discounts.
              Bar width = contribution magnitude.
            </div>

            <ResponsiveContainer width="100%" height={420}>
              <BarChart
                data={waterfallData}
                layout="vertical"
                margin={{ top: 4, right: 60, left: 10, bottom: 4 }}
                barSize={18}
              >
                <XAxis type="number" domain={['auto', 'auto']} tick={{ fill: '#3D5A78', fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={v => `₹${v}`} />
                <YAxis type="category" dataKey="name" width={190} tick={{ fill: '#7A9CC0', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <ReferenceLine x={0} stroke="var(--border-2)" strokeWidth={1} />
                <Bar dataKey={d => d.isTotal ? d.contribution : d.contribution} radius={[0, 4, 4, 0]}>
                  {waterfallData.map((entry, index) => (
                    <Cell
                      key={index}
                      fill={entry.isTotal ? '#60A5FA' : entry.positive ? '#00C9B1' : '#EF4444'}
                      fillOpacity={entry.isTotal ? 0.9 : 0.8}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>

            <div style={{ display: 'flex', gap: 20, fontSize: 12, color: 'var(--text-2)', borderTop: '1px solid var(--border)', paddingTop: 12, marginTop: 4 }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 10, height: 10, borderRadius: 2, background: 'var(--teal)', display: 'inline-block' }} />
                Risk-increasing factor
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 10, height: 10, borderRadius: 2, background: 'var(--red)', display: 'inline-block' }} />
                Discount / risk reduction
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 10, height: 10, borderRadius: 2, background: 'var(--blue)', display: 'inline-block' }} />
                Total recommended premium
              </span>
            </div>
          </>
        )}

        {!result && (
          <div style={{ padding: '32px 0', textAlign: 'center', color: 'var(--text-3)', fontSize: 13 }}>
            Configure rider profile above and click Calculate Premium to see the XGBoost + LightGBM SHAP breakdown
          </div>
        )}
      </div>
    </>
  )
}
