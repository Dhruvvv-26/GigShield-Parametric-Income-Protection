import { useEffect, useState, useCallback } from 'react'
import { formatDistanceToNow } from 'date-fns'
import type { Claim } from '../lib/types'
import { fetchClaims, approveClaim, blockClaim } from '../lib/api'

function scoreColor(v: number) {
  if (v < 0.3) return 'var(--teal)'
  if (v < 0.65) return 'var(--amber)'
  return 'var(--red)'
}

function ScoreBar({ value }: { value: number }) {
  const c = scoreColor(value)
  return (
    <div className="score-bar-wrap">
      <div className="score-bar-track">
        <div className="score-bar-fill" style={{ width: `${value * 100}%`, background: c }} />
      </div>
      <span className="score-num" style={{ color: c }}>{value.toFixed(2)}</span>
    </div>
  )
}

function LayerBars({ scores }: { scores: Claim['layer_scores'] }) {
  const layers: [string, number][] = [
    ['GPS', scores.gps],
    ['Sensor', scores.sensor],
    ['Network', scores.network],
    ['Behav.', scores.behavioral],
  ]
  return (
    <div className="layer-grid">
      {layers.map(([label, val]) => (
        <div className="layer-cell" key={label}>
          <div className="layer-label">{label}</div>
          <div className="layer-val" style={{ color: scoreColor(val) }}>{val.toFixed(2)}</div>
          <div style={{ height: 3, background: 'var(--bg-base)', borderRadius: 2, overflow: 'hidden', marginTop: 3 }}>
            <div style={{ height: '100%', width: `${val * 100}%`, background: scoreColor(val), borderRadius: 2 }} />
          </div>
        </div>
      ))}
    </div>
  )
}

function StatusBadge({ status }: { status: Claim['status'] }) {
  const map: Record<string, string> = {
    AUTO_APPROVED: 'badge-teal',
    SOFT_HOLD: 'badge-amber',
    BLOCKED: 'badge-red',
    PENDING: 'badge-gray',
  }
  return <span className={`badge ${map[status] ?? 'badge-gray'}`}>{status.replace('_', ' ')}</span>
}

function EventBadge({ type }: { type: string }) {
  const icons: Record<string, string> = { aqi: '☁', rain: '⛈', heat: '♨', cyclone: '🌀', bandh: '🔒' }
  return (
    <span style={{ fontSize: 12, color: 'var(--text-2)', display: 'flex', alignItems: 'center', gap: 4 }}>
      <span style={{ fontSize: 15 }}>{icons[type] ?? '⚡'}</span>
      {type.toUpperCase()}
    </span>
  )
}

export default function FraudQueue({ live }: { live: boolean }) {
  const [claims, setClaims] = useState<Claim[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [filter, setFilter] = useState<'ALL' | 'SOFT_HOLD' | 'BLOCKED' | 'AUTO_APPROVED'>('ALL')
  const [acting, setActing] = useState<string | null>(null)

  const load = useCallback(async () => {
    const { data } = await fetchClaims()
    setClaims(data)
    setLoading(false)
  }, [])

  useEffect(() => {
    load()
    const iv = setInterval(load, 8000)
    return () => clearInterval(iv)
  }, [load])

  async function handleApprove(claimId: string) {
    setActing(claimId)
    await approveClaim(claimId)
    setClaims(prev => prev.map(c => c.claim_id === claimId ? { ...c, status: 'AUTO_APPROVED' } : c))
    setActing(null)
  }

  async function handleBlock(claimId: string) {
    setActing(claimId)
    await blockClaim(claimId)
    setClaims(prev => prev.map(c => c.claim_id === claimId ? { ...c, status: 'BLOCKED', payout_amount: 0 } : c))
    setActing(null)
  }

  const filtered = filter === 'ALL' ? claims : claims.filter(c => c.status === filter)
  const softHolds = claims.filter(c => c.status === 'SOFT_HOLD').length
  const blocked = claims.filter(c => c.status === 'BLOCKED').length

  return (
    <>
      <div className="page-header">
        <div className="page-title">Fraud Queue</div>
        <div className="page-sub">5-layer adversarial defense — real-time claim review with per-signal breakdown</div>
      </div>

      {!live && (
        <div className="demo-banner">
          ⚡ Demo mode — simulated claims with realistic fraud signal data. Backend polling active.
        </div>
      )}

      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        {(['ALL', 'SOFT_HOLD', 'BLOCKED', 'AUTO_APPROVED'] as const).map(f => (
          <button
            key={f}
            className={`btn ${filter === f ? 'btn-teal' : 'btn-ghost'}`}
            onClick={() => setFilter(f)}
          >
            {f === 'ALL' ? `All (${claims.length})` :
             f === 'SOFT_HOLD' ? `Soft Hold (${softHolds})` :
             f === 'BLOCKED' ? `Blocked (${blocked})` : 'Approved'}
          </button>
        ))}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text-2)' }}>
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: live ? 'var(--teal)' : 'var(--amber)', animation: 'pulse-dot 2s ease-in-out infinite' }} />
          {live ? 'Polling every 8s' : 'Mock data — demo mode'}
        </div>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? (
          <div className="loading-wrap">
            <div className="spinner" />
            <span>Loading claims...</span>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Claim ID</th>
                <th>Rider</th>
                <th>Zone</th>
                <th>Event</th>
                <th>Fraud Score</th>
                <th>Layer Signals</th>
                <th>Status</th>
                <th>Payout</th>
                <th>Age</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(claim => (
                <>
                  <tr
                    key={claim.claim_id}
                    className={expanded === claim.claim_id ? 'expanded' : ''}
                    onClick={() => setExpanded(prev => prev === claim.claim_id ? null : claim.claim_id)}
                  >
                    <td>
                      <span className="mono" style={{ fontSize: 12, color: 'var(--text-2)' }}>
                        {claim.claim_id}
                      </span>
                    </td>
                    <td>
                      <div style={{ fontWeight: 500 }}>{claim.rider_name}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'var(--font-mono)' }}>
                        {claim.worker_id.slice(0, 8)}…
                      </div>
                    </td>
                    <td>
                      <span className="mono" style={{ fontSize: 12, color: 'var(--teal)' }}>{claim.zone}</span>
                    </td>
                    <td><EventBadge type={claim.event_type} /></td>
                    <td style={{ minWidth: 140 }}><ScoreBar value={claim.fraud_score} /></td>
                    <td><LayerBars scores={claim.layer_scores} /></td>
                    <td><StatusBadge status={claim.status} /></td>
                    <td>
                      <span className="mono" style={{ fontSize: 12, color: claim.payout_amount > 0 ? 'var(--teal)' : 'var(--red)' }}>
                        {claim.payout_amount > 0 ? `₹${claim.payout_amount}` : '—'}
                      </span>
                    </td>
                    <td style={{ fontSize: 12, color: 'var(--text-3)' }}>
                      {formatDistanceToNow(new Date(claim.created_at), { addSuffix: true })}
                    </td>
                  </tr>

                  {expanded === claim.claim_id && (
                    <tr className="detail-row" key={`${claim.claim_id}-detail`}>
                      <td colSpan={9}>
                        <div className="detail-inner">
                          <div className="detail-section">
                            <div className="detail-label">Fraud flags detected</div>
                            {claim.fraud_flags.length === 0 ? (
                              <span style={{ fontSize: 12, color: 'var(--teal)' }}>✓ No anomalies detected</span>
                            ) : (
                              <div className="flag-list">
                                {claim.fraud_flags.map(f => (
                                  <span key={f} className="flag-tag">{f}</span>
                                ))}
                              </div>
                            )}

                            <div className="detail-label" style={{ marginTop: 12 }}>Layer 5 Bouncer</div>
                            <span style={{ fontSize: 12, color: claim.bouncer_passed ? 'var(--teal)' : 'var(--red)' }}>
                              {claim.bouncer_passed ? '✓ Passed — biometric time lock + zone check' : '✗ Hard rejected — did not pass Bouncer'}
                            </span>

                            <div className="detail-label" style={{ marginTop: 12 }}>Event details</div>
                            <span className="mono" style={{ fontSize: 12, color: 'var(--text-2)' }}>
                              {claim.event_type.toUpperCase()} · metric={claim.metric_value} · zone={claim.zone}
                            </span>
                          </div>

                          <div className="detail-section">
                            <div className="detail-label">Full score breakdown</div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                              {[
                                { label: 'GPS Physics (30%)', val: claim.layer_scores.gps, weight: 0.30 },
                                { label: 'Device Sensor (25%)', val: claim.layer_scores.sensor, weight: 0.25 },
                                { label: 'Network Geo (25%)', val: claim.layer_scores.network, weight: 0.25 },
                                { label: 'Behavioral (20%)', val: claim.layer_scores.behavioral, weight: 0.20 },
                              ].map(({ label, val }) => (
                                <div key={label}>
                                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                                    <span style={{ color: 'var(--text-2)' }}>{label}</span>
                                    <span className="mono" style={{ color: scoreColor(val) }}>{val.toFixed(3)}</span>
                                  </div>
                                  <div style={{ height: 5, background: 'var(--bg-base)', borderRadius: 3, overflow: 'hidden' }}>
                                    <div style={{ height: '100%', width: `${val * 100}%`, background: scoreColor(val), borderRadius: 3, transition: 'width 0.5s' }} />
                                  </div>
                                </div>
                              ))}
                              <div style={{ borderTop: '1px solid var(--border)', paddingTop: 8, display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                                <span style={{ color: 'var(--text-2)', fontWeight: 600 }}>Composite score</span>
                                <span className="mono" style={{ color: scoreColor(claim.fraud_score), fontWeight: 700 }}>
                                  {claim.fraud_score.toFixed(3)}
                                </span>
                              </div>
                            </div>

                            {claim.status === 'SOFT_HOLD' && (
                              <div className="actions-row">
                                <button
                                  className="btn btn-teal"
                                  disabled={acting === claim.claim_id}
                                  onClick={e => { e.stopPropagation(); handleApprove(claim.claim_id) }}
                                >
                                  {acting === claim.claim_id ? 'Processing…' : '✓ Release Full Payout'}
                                </button>
                                <button
                                  className="btn btn-red"
                                  disabled={acting === claim.claim_id}
                                  onClick={e => { e.stopPropagation(); handleBlock(claim.claim_id) }}
                                >
                                  ✗ Block Claim
                                </button>
                              </div>
                            )}
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  )
}
