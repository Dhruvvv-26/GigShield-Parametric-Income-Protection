import { useEffect, useState } from 'react'
import { fetchPaymentSummary } from '../lib/api'
import type { PaymentSummary } from '../lib/types'

const BCR_COLORS = {
  SOLVENT: { bg: 'rgba(0, 255, 135, 0.08)', border: '#00ff87', text: '#00ff87', label: 'SOLVENT' },
  WATCH:   { bg: 'rgba(255, 193, 7, 0.08)',  border: '#ffc107', text: '#ffc107', label: 'WATCH' },
  CRITICAL:{ bg: 'rgba(255, 77, 77, 0.08)',   border: '#ff4d4d', text: '#ff4d4d', label: 'CRITICAL' },
} as const

function MetricCard({ title, value, subtitle, color, icon }: {
  title: string
  value: string
  subtitle: string
  color: string
  icon: string
}) {
  return (
    <div style={{
      background: 'var(--surface)',
      borderRadius: 12,
      padding: '20px 24px',
      border: '1px solid var(--border)',
      flex: '1 1 220px',
      minWidth: 220,
      position: 'relative',
      overflow: 'hidden',
    }}>
      <div style={{ position: 'absolute', top: 12, right: 16, fontSize: 28, opacity: 0.15 }}>{icon}</div>
      <div style={{ fontSize: 11, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>
        {title}
      </div>
      <div style={{ fontSize: 28, fontWeight: 700, color, fontFamily: 'var(--font-mono)', lineHeight: 1 }}>
        {value}
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-2)', marginTop: 6 }}>
        {subtitle}
      </div>
    </div>
  )
}

function BCRGauge({ bcr, status }: { bcr: number; status: string }) {
  const colors = BCR_COLORS[status as keyof typeof BCR_COLORS] || BCR_COLORS.SOLVENT
  const angle = Math.min(bcr / 100 * 180, 180)

  return (
    <div style={{
      background: colors.bg,
      border: `1px solid ${colors.border}`,
      borderRadius: 16,
      padding: '28px 32px',
      flex: '1 1 320px',
      minWidth: 320,
      textAlign: 'center',
    }}>
      <div style={{ fontSize: 12, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: 1.5, marginBottom: 12 }}>
        Burning Cost Rate (30-Day)
      </div>

      {/* SVG Gauge */}
      <svg viewBox="0 0 200 110" width="200" height="110" style={{ margin: '0 auto', display: 'block' }}>
        {/* Background arc */}
        <path
          d="M 20 100 A 80 80 0 0 1 180 100"
          fill="none"
          stroke="var(--border)"
          strokeWidth="10"
          strokeLinecap="round"
        />
        {/* Value arc */}
        <path
          d={`M 20 100 A 80 80 0 ${angle > 90 ? 1 : 0} 1 ${100 + 80 * Math.cos(Math.PI - (angle * Math.PI / 180))} ${100 - 80 * Math.sin((angle * Math.PI / 180))}`}
          fill="none"
          stroke={colors.border}
          strokeWidth="10"
          strokeLinecap="round"
          style={{ transition: 'all 0.8s ease-out' }}
        />
        {/* Value text */}
        <text x="100" y="90" textAnchor="middle" fill={colors.text} fontSize="24" fontWeight="700" fontFamily="var(--font-mono)">
          {bcr.toFixed(1)}%
        </text>
        {/* Labels */}
        <text x="25" y="108" fontSize="9" fill="var(--text-3)">0%</text>
        <text x="170" y="108" fontSize="9" fill="var(--text-3)">100%</text>
      </svg>

      <div style={{
        display: 'inline-block',
        marginTop: 8,
        padding: '4px 14px',
        borderRadius: 20,
        background: colors.bg,
        border: `1px solid ${colors.border}`,
        color: colors.text,
        fontSize: 12,
        fontWeight: 600,
        letterSpacing: 0.5,
      }}>
        {colors.label}
      </div>

      <div style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 8 }}>
        {bcr < 70 ? 'Portfolio is actuarially solvent' : bcr <= 85 ? 'Monitor — approaching breakeven' : 'Unsustainable — adjust premiums or tighten fraud filters'}
      </div>
    </div>
  )
}

export default function ActuarialDashboard({ live }: { live: boolean }) {
  const [summary, setSummary] = useState<PaymentSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      const s = await fetchPaymentSummary()
      setSummary(s.data)
      setLoading(false)
    }
    load()
    const interval = setInterval(load, 30000)
    return () => clearInterval(interval)
  }, [])

  if (loading || !summary) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh', color: 'var(--text-3)' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 32, marginBottom: 8, animation: 'pulse-dot 1s ease-in-out infinite' }}>◈</div>
          Loading actuarial data...
        </div>
      </div>
    )
  }

  const netPosition = summary.trailing_30d_premiums - summary.trailing_30d_payouts
  const netColor = netPosition >= 0 ? '#00ff87' : '#ff4d4d'

  return (
    <div style={{ maxWidth: 1100 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0 }}>Actuarial Dashboard</h1>
        <span style={{
          fontSize: 10,
          padding: '2px 8px',
          borderRadius: 8,
          background: live ? 'rgba(0,255,135,0.1)' : 'rgba(255,193,7,0.1)',
          color: live ? '#00ff87' : '#ffc107',
          border: `1px solid ${live ? '#00ff87' : '#ffc107'}`,
        }}>
          {live ? 'LIVE' : 'DEMO'}
        </span>
      </div>

      {/* Top row: BCR Gauge + metric cards */}
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 20 }}>
        <BCRGauge bcr={summary.burning_cost_rate} status={summary.bcr_status} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, flex: '1 1 450px', minWidth: 450 }}>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <MetricCard
              title="Loss Ratio (7d)"
              value={`${(summary.loss_ratio * 100).toFixed(1)}%`}
              subtitle="Target: ≤65%"
              color={summary.loss_ratio <= 0.65 ? '#00ff87' : '#ff4d4d'}
              icon="📊"
            />
            <MetricCard
              title="Reserve Ratio"
              value={`${summary.reserve_ratio.toFixed(1)}%`}
              subtitle="Premium surplus"
              color={summary.reserve_ratio > 30 ? '#00ff87' : '#ffc107'}
              icon="🛡️"
            />
          </div>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <MetricCard
              title="30-Day Net"
              value={`₹${Math.abs(netPosition).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`}
              subtitle={netPosition >= 0 ? 'Surplus' : 'Deficit'}
              color={netColor}
              icon={netPosition >= 0 ? '📈' : '📉'}
            />
            <MetricCard
              title="Active Policies"
              value={summary.active_policies.toString()}
              subtitle="Currently covered riders"
              color="var(--text-1)"
              icon="📋"
            />
          </div>
        </div>
      </div>

      {/* Financial summary table */}
      <div style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        overflow: 'hidden',
      }}>
        <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)', fontSize: 13, fontWeight: 600 }}>
          Trailing 30-Day Financials
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <tbody>
            {[
              ['Premiums Collected (30d)', `₹${summary.trailing_30d_premiums.toLocaleString('en-IN')}`, '#00ff87'],
              ['Payouts Disbursed (30d)', `₹${summary.trailing_30d_payouts.toLocaleString('en-IN')}`, '#ff4d4d'],
              ['Net Position', `₹${Math.abs(netPosition).toLocaleString('en-IN')}`, netColor],
              ['Burning Cost Rate', `${summary.burning_cost_rate.toFixed(1)}%`, BCR_COLORS[summary.bcr_status as keyof typeof BCR_COLORS]?.text || '#00ff87'],
              ['Claims This Week', summary.claims_pending.toString(), 'var(--text-1)'],
              ['Avg Payout', `₹${(summary.total_payouts / Math.max(summary.claims_pending, 1)).toFixed(0)}`, 'var(--text-1)'],
            ].map(([label, value, color], i) => (
              <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={{ padding: '10px 20px', fontSize: 13, color: 'var(--text-2)' }}>{label}</td>
                <td style={{ padding: '10px 20px', fontSize: 14, fontWeight: 600, textAlign: 'right', fontFamily: 'var(--font-mono)', color: color as string }}>
                  {value}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* BCR Status Banner */}
      {summary.bcr_status === 'CRITICAL' && (
        <div style={{
          marginTop: 16,
          padding: '12px 20px',
          background: 'rgba(255, 77, 77, 0.08)',
          border: '1px solid #ff4d4d',
          borderRadius: 10,
          color: '#ff4d4d',
          fontSize: 13,
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        }}>
          <span style={{ fontSize: 18 }}>⚠️</span>
          <span>
            BCR is above 85% — the portfolio is operating at an <strong>actuarial deficit</strong>.
            Consider raising premiums, tightening fraud filters, or adjusting zone risk multipliers.
          </span>
        </div>
      )}
    </div>
  )
}
