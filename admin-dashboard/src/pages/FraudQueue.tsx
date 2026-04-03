import React, { useState } from 'react'

interface Claim {
  id: string
  workerId: string
  workerName: string
  zone: string
  city: string
  triggerType: string
  tier: string
  amount: number
  fraudScore: number
  status: 'soft_hold' | 'blocked'
  flags: string[]
  timestamp: string
}

const MOCK_CLAIMS: Claim[] = [
  { id: 'CLM-001', workerId: 'WRK-A1B2', workerName: 'Rahul Kumar', zone: 'delhi_rohini', city: 'Delhi NCR', triggerType: 'aqi', tier: 'tier2', amount: 300, fraudScore: 0.72, status: 'soft_hold', flags: ['GPS_LOW_ACCURACY_85m', 'ELEVATED_BURST_35_CLAIMS'], timestamp: '2026-04-02T14:30:00Z' },
  { id: 'CLM-002', workerId: 'WRK-C3D4', workerName: 'Priya Sharma', zone: 'mumbai_powai', city: 'Mumbai', triggerType: 'heavy_rain', tier: 'tier1', amount: 200, fraudScore: 0.68, status: 'soft_hold', flags: ['IP_GPS_DELTA_3.2km'], timestamp: '2026-04-02T13:15:00Z' },
  { id: 'CLM-003', workerId: 'WRK-E5F6', workerName: 'Amit Patel', zone: 'delhi_dwarka', city: 'Delhi NCR', triggerType: 'aqi', tier: 'tier1', amount: 150, fraudScore: 0.91, status: 'blocked', flags: ['MOCK_LOCATION_DETECTED', 'GPS_INSTANT_LOCK_120ms', 'DEVICE_STATIONARY_ACCEL_0.03', 'COORDINATED_BURST_142'], timestamp: '2026-04-02T12:45:00Z' },
  { id: 'CLM-004', workerId: 'WRK-G7H8', workerName: 'Sanjay Verma', zone: 'kolkata_park_street', city: 'Kolkata', triggerType: 'aqi', tier: 'tier1', amount: 150, fraudScore: 0.89, status: 'blocked', flags: ['GPS_ZERO_VARIANCE_0.0003m', 'GPS_INSTANT_LOCK_80ms', 'ZERO_TOWER_HANDOFFS'], timestamp: '2026-04-02T11:20:00Z' },
  { id: 'CLM-005', workerId: 'WRK-I9J0', workerName: 'Vijay Singh', zone: 'delhi_laxmi_nagar', city: 'Delhi NCR', triggerType: 'aqi', tier: 'tier1', amount: 150, fraudScore: 0.66, status: 'soft_hold', flags: ['DEVICE_LOW_ACCEL_0.42'], timestamp: '2026-04-02T10:50:00Z' },
]

export default function FraudQueue() {
  const [claims, setClaims] = useState<Claim[]>(MOCK_CLAIMS)

  const handleApprove = (id: string) => {
    setClaims(prev => prev.filter(c => c.id !== id))
  }

  const handleBlock = (id: string) => {
    setClaims(prev => prev.map(c => c.id === id ? { ...c, status: 'blocked' as const } : c))
  }

  const softHoldCount = claims.filter(c => c.status === 'soft_hold').length
  const blockedCount = claims.filter(c => c.status === 'blocked').length

  return (
    <div>
      <div className="page-header">
        <h2>Fraud Review Queue</h2>
        <p>Claims requiring manual review — soft holds and blocked claims</p>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-value" style={{ color: '#FFB74D' }}>{softHoldCount}</div>
          <div className="stat-label">Soft Holds</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: '#FF5252' }}>{blockedCount}</div>
          <div className="stat-label">Blocked</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{claims.length}</div>
          <div className="stat-label">Total in Queue</div>
        </div>
      </div>

      <div className="card">
        <table className="data-table">
          <thead>
            <tr>
              <th>Claim ID</th>
              <th>Rider</th>
              <th>Zone</th>
              <th>Trigger</th>
              <th>Amount</th>
              <th>Score</th>
              <th>Status</th>
              <th>Flags</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {claims.map(claim => (
              <tr key={claim.id}>
                <td style={{ fontFamily: 'monospace', fontSize: 13 }}>{claim.id}</td>
                <td>
                  <div>{claim.workerName}</div>
                  <div style={{ color: 'var(--text-muted)', fontSize: 11 }}>{claim.workerId}</div>
                </td>
                <td>
                  <div>{claim.zone.replace(/_/g, ' ')}</div>
                  <div style={{ color: 'var(--text-muted)', fontSize: 11 }}>{claim.city}</div>
                </td>
                <td>
                  <span className={`badge badge-${claim.tier}`}>{claim.tier}</span>
                  <div style={{ color: 'var(--text-dim)', fontSize: 11, marginTop: 2 }}>{claim.triggerType}</div>
                </td>
                <td style={{ fontWeight: 600 }}>₹{claim.amount}</td>
                <td>
                  <span style={{
                    color: claim.fraudScore >= 0.85 ? '#FF5252' : claim.fraudScore >= 0.65 ? '#FFB74D' : '#00E676',
                    fontWeight: 700,
                    fontSize: 16,
                  }}>
                    {claim.fraudScore.toFixed(2)}
                  </span>
                </td>
                <td><span className={`badge badge-${claim.status.replace('_', '-')}`}>{claim.status.replace('_', ' ')}</span></td>
                <td>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, maxWidth: 200 }}>
                    {claim.flags.map((flag, i) => (
                      <span key={i} style={{
                        background: 'rgba(255, 82, 82, 0.1)',
                        color: '#FF8A80',
                        padding: '2px 6px',
                        borderRadius: 4,
                        fontSize: 10,
                        fontFamily: 'monospace',
                      }}>{flag}</span>
                    ))}
                  </div>
                </td>
                <td>
                  <div style={{ display: 'flex', gap: 6 }}>
                    {claim.status === 'soft_hold' && (
                      <>
                        <button className="btn btn-success" onClick={() => handleApprove(claim.id)}>Approve</button>
                        <button className="btn btn-danger" onClick={() => handleBlock(claim.id)}>Block</button>
                      </>
                    )}
                    {claim.status === 'blocked' && (
                      <button className="btn btn-success" onClick={() => handleApprove(claim.id)}>Override</button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
