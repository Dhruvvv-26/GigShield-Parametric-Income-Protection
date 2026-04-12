import { useEffect, useState } from 'react'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import type { PaymentSummary, TriggerStatus } from '../lib/types'
import { fetchTriggerStatus } from '../lib/api'
import { formatDistanceToNow } from 'date-fns'

const TREND_DATA = [
  { day: 'Mar 28', premiums: 184000, payouts: 118000 },
  { day: 'Mar 29', premiums: 197000, payouts: 134000 },
  { day: 'Mar 30', premiums: 212000, payouts: 142000 },
  { day: 'Mar 31', premiums: 223000, payouts: 148000 },
  { day: 'Apr 01', premiums: 238000, payouts: 155000 },
  { day: 'Apr 02', premiums: 255000, payouts: 164000 },
  { day: 'Apr 03', premiums: 278000, payouts: 178000 },
  { day: 'Apr 04', premiums: 289000, payouts: 191000 },
  { day: 'Apr 05', premiums: 305000, payouts: 202000 },
  { day: 'Apr 06', premiums: 319000, payouts: 207000 },
]

function fmt(n: number) {
  if (n >= 100000) return `₹${(n / 100000).toFixed(1)}L`
  if (n >= 1000) return `₹${(n / 1000).toFixed(0)}K`
  return `₹${n}`
}

function ScoreGauge({ value, label }: { value: number; label: string }) {
  const color = value < 0.5 ? 'var(--teal)' : value < 0.75 ? 'var(--amber)' : 'var(--red)'
  const pct = Math.round(value * 100)
  const r = 36, cx = 44, cy = 44
  const circ = 2 * Math.PI * r
  const dash = circ * (1 - value)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
      <svg width={88} height={88} viewBox="0 0 88 88">
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--bg-base)" strokeWidth={8} />
        <circle
          cx={cx} cy={cy} r={r} fill="none" stroke={color} strokeWidth={8}
          strokeDasharray={circ} strokeDashoffset={dash}
          strokeLinecap="round"
          style={{ transform: 'rotate(-90deg)', transformOrigin: '44px 44px', transition: 'stroke-dashoffset 1s' }}
        />
        <text x={cx} y={cy} textAnchor="middle" dominantBaseline="central"
          fill={color} fontSize={16} fontWeight={700} fontFamily="IBM Plex Mono">
          {pct}%
        </text>
      </svg>
      <div style={{ fontSize: 11, color: 'var(--text-3)', textAlign: 'center', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{label}</div>
    </div>
  )
}

export default function LiveMetrics({
  summary, triggerStatus, live,
}: { summary: PaymentSummary | null; triggerStatus: TriggerStatus | null; live: boolean }) {
  const [ts, setTs] = useState<TriggerStatus | null>(triggerStatus)
  useEffect(() => { if (triggerStatus) setTs(triggerStatus) }, [triggerStatus])

  const s = summary ?? {
    total_premiums: 1287400, total_payouts: 836810, loss_ratio: 0.65,
    active_policies: 183, claims_pending: 2, fraud_blocks_24h: 17,
    auto_approved_24h: 94, soft_holds_24h: 5,
  }

  const pctSaved = s.fraud_blocks_24h > 0 ? Math.round((s.fraud_blocks_24h / (s.fraud_blocks_24h + s.auto_approved_24h)) * 100) : 0

  return (
    <>
      <div className="page-header">
        <div className="page-title">Live Metrics</div>
        <div className="page-sub">Real-time financial health and fraud prevention — KavachAI Phase 3</div>
      </div>

      {!live && (
        <div className="demo-banner">
          ⚡ Demo mode — showing realistic mock data. Start the Docker stack to stream live metrics.
        </div>
      )}

      <div className="metrics-grid">
        <div className="metric-card teal">
          <div className="metric-label">Total Premiums</div>
          <div className="metric-value">{fmt(s.total_premiums)}</div>
          <div className="metric-sub">Collected this period</div>
        </div>
        <div className="metric-card amber">
          <div className="metric-label">Total Payouts</div>
          <div className="metric-value">{fmt(s.total_payouts)}</div>
          <div className="metric-sub">Disbursed to riders</div>
        </div>
        <div className="metric-card" style={{ borderTopColor: s.loss_ratio < 0.7 ? 'var(--teal)' : 'var(--red)' }}>
          <div className="metric-label">Loss Ratio</div>
          <div className="metric-value" style={{ color: s.loss_ratio < 0.7 ? 'var(--teal)' : 'var(--red)' }}>
            {(s.loss_ratio * 100).toFixed(1)}%
          </div>
          <div className="metric-sub">Target: &lt;70% — IRDAI parametric standard</div>
        </div>
        <div className="metric-card blue">
          <div className="metric-label">Active Policies</div>
          <div className="metric-value">{s.active_policies}</div>
          <div className="metric-sub">Weekly coverage live</div>
        </div>
        <div className="metric-card red">
          <div className="metric-label">Fraud Blocks (24h)</div>
          <div className="metric-value">{s.fraud_blocks_24h}</div>
          <div className="metric-sub">{pctSaved}% of submissions blocked</div>
        </div>
        <div className="metric-card purple">
          <div className="metric-label">Claims Pending</div>
          <div className="metric-value">{s.claims_pending}</div>
          <div className="metric-sub">Awaiting manual review</div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 280px', gap: 16 }}>
        <div className="card">
          <div className="card-header">
            <div className="card-title">Premium vs Payout Trend (10-day)</div>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={TREND_DATA} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
              <defs>
                <linearGradient id="gPrem" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#00C9B1" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#00C9B1" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gPay" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#F59E0B" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#F59E0B" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="day" tick={{ fill: '#3D5A78', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tickFormatter={v => fmt(v)} tick={{ fill: '#3D5A78', fontSize: 11 }} axisLine={false} tickLine={false} width={56} />
              <Tooltip
                contentStyle={{ background: '#121F35', border: '1px solid rgba(0,201,177,0.2)', borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: '#7A9CC0' }}
                formatter={(v: number) => [fmt(v), '']}
              />
              <Area type="monotone" dataKey="premiums" stroke="#00C9B1" strokeWidth={2} fill="url(#gPrem)" name="Premiums" />
              <Area type="monotone" dataKey="payouts" stroke="#F59E0B" strokeWidth={2} fill="url(#gPay)" name="Payouts" />
              <Legend wrapperStyle={{ fontSize: 12, color: '#7A9CC0', paddingTop: 8 }} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div className="card-header" style={{ marginBottom: 4 }}>
            <div className="card-title">Health Gauges</div>
          </div>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', justifyContent: 'center' }}>
            <ScoreGauge value={s.loss_ratio} label="Loss ratio" />
            <ScoreGauge value={s.fraud_blocks_24h / (s.fraud_blocks_24h + s.auto_approved_24h + 0.01)} label="Fraud rate" />
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-2)', textAlign: 'center', borderTop: '1px solid var(--border)', paddingTop: 10 }}>
            Operating margin: {fmt(s.total_premiums - s.total_payouts)}
          </div>
        </div>
      </div>

      {ts?.active_triggers?.length ? (
        <div className="card">
          <div className="card-header">
            <div className="card-title">Active Triggers Now</div>
            <span className="badge badge-amber">LIVE</span>
          </div>
          <table className="data-table">
            <thead><tr><th>Zone</th><th>Event</th><th>Metric</th><th>Tier</th><th>Age</th></tr></thead>
            <tbody>
              {ts.active_triggers.map((t, i) => (
                <tr key={i}>
                  <td><span className="mono" style={{ color: 'var(--teal)' }}>{t.zone}</span></td>
                  <td><span className="badge badge-amber">{t.event_type.toUpperCase()}</span></td>
                  <td><span className="mono">{t.metric_value}</span></td>
                  <td>
                    <span className="badge" style={{
                      background: t.tier === 3 ? 'var(--red-glow)' : t.tier === 2 ? 'var(--amber-glow)' : 'var(--teal-glow)',
                      color: t.tier === 3 ? 'var(--red)' : t.tier === 2 ? 'var(--amber)' : 'var(--teal)',
                      border: `1px solid ${t.tier === 3 ? 'var(--red)' : t.tier === 2 ? 'var(--amber)' : 'var(--teal)'}`,
                    }}>T{t.tier}</span>
                  </td>
                  <td style={{ color: 'var(--text-2)', fontSize: 12 }}>
                    {formatDistanceToNow(new Date(t.triggered_at), { addSuffix: true })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </>
  )
}
