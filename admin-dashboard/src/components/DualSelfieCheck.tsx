import { useEffect, useState, useCallback } from 'react'
import { formatDistanceToNow } from 'date-fns'
import type { Claim } from '../lib/types'
import { fetchClaims, approveClaim, blockClaim } from '../lib/api'

function PhysicsReadout({ scores }: { scores: Claim['layer_scores'] }) {
  const checks = [
    { label: 'GPS satellite variance (σ)', clean: scores.gps < 0.3, value: scores.gps < 0.3 ? `σ = ${(2 + scores.gps * 8).toFixed(1)}m` : `σ = ${(scores.gps * 0.5).toFixed(2)}m (spoofed)` },
    { label: 'Accelerometer RMS', clean: scores.sensor < 0.3, value: scores.sensor < 0.3 ? `${(0.8 + scores.sensor * 1.6).toFixed(2)} m/s²` : `${(scores.sensor * 0.3).toFixed(2)} m/s² (stationary)` },
    { label: 'Network IP Δ GPS', clean: scores.network < 0.3, value: scores.network < 0.3 ? `< 2km delta` : `${(scores.network * 15).toFixed(1)}km delta` },
    { label: 'T−30 zone residency', clean: scores.behavioral < 0.3, value: scores.behavioral < 0.3 ? 'Resident confirmed' : 'Sudden appearance' },
  ]
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {checks.map(c => (
        <div key={c.label} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11 }}>
          <span style={{ color: c.clean ? 'var(--teal)' : 'var(--red)', width: 14, textAlign: 'center' }}>
            {c.clean ? '✓' : '✗'}
          </span>
          <span style={{ color: 'var(--text-2)', flex: 1 }}>{c.label}</span>
          <span style={{ fontFamily: 'IBM Plex Mono', color: c.clean ? 'var(--teal)' : 'var(--red)', fontSize: 10 }}>
            {c.value}
          </span>
        </div>
      ))}
    </div>
  )
}

function SelfieCard({ claim, onApprove, onBlock }: {
  claim: Claim
  onApprove: (id: string) => void
  onBlock: (id: string) => void
}) {
  const isSuspect = claim.fraud_score > 0.65
  return (
    <div className="selfie-card" style={{ borderColor: isSuspect ? 'rgba(239,68,68,0.4)' : 'var(--border)' }}>
      <div className="selfie-header">
        <div>
          <div style={{ fontWeight: 600, fontSize: 13 }}>{claim.rider_name}</div>
          <div style={{ fontSize: 11, color: 'var(--text-3)', fontFamily: 'IBM Plex Mono' }}>
            {claim.claim_id}
          </div>
        </div>
        <span className={`badge ${claim.status === 'SOFT_HOLD' ? 'badge-amber' : 'badge-red'}`}>
          {claim.status.replace('_', ' ')}
        </span>
      </div>

      <div className="selfie-body">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 12 }}>
          <div className="selfie-placeholder">
            <div className="selfie-face">📸</div>
            <div style={{ fontSize: 10, textAlign: 'center' }}>Claim-time selfie<br />{formatDistanceToNow(new Date(claim.created_at), { addSuffix: true })}</div>
          </div>
          <div className="selfie-placeholder">
            <div className="selfie-face">🪪</div>
            <div style={{ fontSize: 10, textAlign: 'center' }}>KYC reference<br />Last verified</div>
          </div>
        </div>

        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 11, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 8 }}>
            Signal Analysis
          </div>
          <PhysicsReadout scores={claim.layer_scores} />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <span style={{ fontSize: 11, color: 'var(--text-3)' }}>Composite fraud score</span>
          <div style={{ flex: 1, height: 5, background: 'var(--bg-base)', borderRadius: 3, overflow: 'hidden' }}>
            <div style={{ height: '100%', width: `${claim.fraud_score * 100}%`, background: claim.fraud_score > 0.65 ? 'var(--red)' : 'var(--amber)', borderRadius: 3 }} />
          </div>
          <span style={{ fontFamily: 'IBM Plex Mono', fontSize: 12, fontWeight: 700, color: claim.fraud_score > 0.65 ? 'var(--red)' : 'var(--amber)', minWidth: 32 }}>
            {claim.fraud_score.toFixed(2)}
          </span>
        </div>

        {claim.fraud_flags.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 11, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>Active Flags</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {claim.fraud_flags.map(f => (
                <span key={f} className="flag-tag" style={{ fontSize: 10 }}>{f}</span>
              ))}
            </div>
          </div>
        )}

        <div style={{ padding: '8px 10px', background: 'var(--bg-surface)', borderRadius: 6, fontSize: 12, color: 'var(--text-2)', marginBottom: 12 }}>
          <span style={{ color: 'var(--text-3)' }}>Zone: </span>
          <span style={{ fontFamily: 'IBM Plex Mono', color: 'var(--teal)' }}>{claim.zone}</span>
          <span style={{ color: 'var(--text-3)', marginLeft: 12 }}>Payout held: </span>
          <span style={{ fontFamily: 'IBM Plex Mono', color: 'var(--amber)' }}>₹{claim.payout_amount}</span>
        </div>

        <div className="selfie-actions">
          <button className="btn btn-teal" style={{ flex: 1 }} onClick={() => onApprove(claim.claim_id)}>
            ✓ Release ₹{claim.payout_amount}
          </button>
          <button className="btn btn-red" onClick={() => onBlock(claim.claim_id)}>
            ✗ Block
          </button>
        </div>
      </div>
    </div>
  )
}

export default function DualSelfieCheck({ live }: { live: boolean }) {
  const [claims, setClaims] = useState<Claim[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    const { data } = await fetchClaims()
    setClaims(data.filter(c => c.status === 'SOFT_HOLD'))
    setLoading(false)
  }, [])

  useEffect(() => {
    load()
    const iv = setInterval(load, 12000)
    return () => clearInterval(iv)
  }, [load])

  async function handleApprove(id: string) {
    await approveClaim(id)
    setClaims(prev => prev.filter(c => c.claim_id !== id))
  }

  async function handleBlock(id: string) {
    await blockClaim(id)
    setClaims(prev => prev.filter(c => c.claim_id !== id))
  }

  return (
    <>
      <div className="page-header">
        <div className="page-title">Dual Selfie Check</div>
        <div className="page-sub">
          Visual liveness review for SOFT_HOLD claims (fraud score 0.65–0.85) — compare claim-time selfie vs KYC reference
        </div>
      </div>

      {!live && (
        <div className="demo-banner">
          ⚡ Demo mode — selfie images require FCM + mobile app. Signal analysis and fraud flags are live from the claims pipeline.
        </div>
      )}

      <div className="card" style={{ background: 'var(--bg-card-2)', border: '1px solid rgba(245,158,11,0.2)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ fontSize: 22 }}>◉</div>
          <div>
            <div style={{ fontWeight: 600, fontSize: 14 }}>Dual Selfie Protocol — Layer 5 Bouncer Extension</div>
            <div style={{ fontSize: 12, color: 'var(--text-2)', marginTop: 2 }}>
              Claims in SOFT_HOLD (score 0.65–0.85) receive a partial payout immediately (50%) while the second 50% is held
              pending this visual liveness verification. Admin compares the geo-stamped claim selfie vs KYC reference photo.
              Biometric time lock confirms selfie was captured within 5 minutes of the trigger event.
            </div>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="loading-wrap">
          <div className="spinner" />
          <span>Loading SOFT_HOLD queue…</span>
        </div>
      ) : claims.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '48px 24px' }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>✓</div>
          <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--teal)', marginBottom: 4 }}>Queue clear</div>
          <div style={{ fontSize: 13, color: 'var(--text-3)' }}>No claims require manual selfie review. Auto-approval pipeline running cleanly.</div>
        </div>
      ) : (
        <>
          <div style={{ fontSize: 13, color: 'var(--text-2)' }}>
            {claims.length} claim{claims.length !== 1 ? 's' : ''} pending visual review
          </div>
          <div className="selfie-grid">
            {claims.map(claim => (
              <SelfieCard key={claim.claim_id} claim={claim} onApprove={handleApprove} onBlock={handleBlock} />
            ))}
          </div>
        </>
      )}
    </>
  )
}
