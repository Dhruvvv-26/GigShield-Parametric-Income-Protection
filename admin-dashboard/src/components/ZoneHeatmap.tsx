import { useEffect, useState } from 'react'
import { MapContainer, TileLayer, CircleMarker, Popup, Tooltip as LTooltip } from 'react-leaflet'
import type { Zone } from '../lib/types'
import { fetchZones, fetchTriggerStatus } from '../lib/api'
import type { ActiveTrigger } from '../lib/types'

function riskColor(score: number): string {
  if (score < 0.35) return '#00C9B1'
  if (score < 0.55) return '#4CAF50'
  if (score < 0.70) return '#F59E0B'
  if (score < 0.85) return '#EF8C34'
  return '#EF4444'
}

function riskLabel(score: number): string {
  if (score < 0.35) return 'Low'
  if (score < 0.55) return 'Moderate'
  if (score < 0.70) return 'Elevated'
  if (score < 0.85) return 'High'
  return 'Critical'
}

function CityLegend() {
  const entries = [
    { label: 'Low risk', color: '#00C9B1' },
    { label: 'Moderate', color: '#4CAF50' },
    { label: 'Elevated', color: '#F59E0B' },
    { label: 'High', color: '#EF8C34' },
    { label: 'Critical', color: '#EF4444' },
  ]
  return (
    <div style={{
      position: 'absolute', bottom: 20, left: 20, zIndex: 1000,
      background: 'rgba(12,22,40,0.92)', border: '1px solid rgba(0,201,177,0.2)',
      borderRadius: 8, padding: '10px 14px',
      backdropFilter: 'blur(8px)', display: 'flex', flexDirection: 'column', gap: 6,
    }}>
      <div style={{ fontSize: 10, color: '#3D5A78', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 2 }}>Zone Risk Level</div>
      {entries.map(e => (
        <div key={e.label} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#7A9CC0' }}>
          <span style={{ width: 12, height: 12, borderRadius: '50%', background: e.color, display: 'inline-block', opacity: 0.85 }} />
          {e.label}
        </div>
      ))}
    </div>
  )
}

export default function ZoneHeatmap({ live }: { live: boolean }) {
  const [zones, setZones] = useState<Zone[]>([])
  const [activeTriggers, setActiveTriggers] = useState<ActiveTrigger[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      const [z, t] = await Promise.all([fetchZones(), fetchTriggerStatus()])
      setZones(z.data)
      setActiveTriggers(t.data.active_triggers ?? [])
      setLoading(false)
    }
    load()
    const iv = setInterval(load, 20000)
    return () => clearInterval(iv)
  }, [])

  const activeZones = new Set(activeTriggers.map(t => t.zone))

  if (loading) {
    return (
      <div className="loading-wrap">
        <div className="spinner" />
        <span>Loading zone data…</span>
      </div>
    )
  }

  return (
    <>
      <div className="page-header">
        <div className="page-title">Zone Risk Heatmap</div>
        <div className="page-sub">PostGIS-backed zone risk overlay — Delhi NCR, Mumbai, Bengaluru · Real-time trigger indicators</div>
      </div>

      {!live && (
        <div className="demo-banner">
          ⚡ Demo mode — zone centroids from PostGIS seed data. Connect to backend for live AQI-weighted risk scores.
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 260px', gap: 16, alignItems: 'start' }}>
        <div className="card" style={{ padding: 0, overflow: 'hidden', position: 'relative' }}>
          <MapContainer
            center={[24.0, 77.5]}
            zoom={5}
            style={{ height: 500 }}
            zoomControl={true}
          >
            <TileLayer
              url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
              attribution='&copy; <a href="https://carto.com/">CARTO</a>'
            />
            {zones.map(zone => {
              const isActive = activeZones.has(zone.zone_id)
              const color = riskColor(zone.risk_score)
              return (
                <CircleMarker
                  key={zone.zone_id}
                  center={[zone.centroid_lat, zone.centroid_lon]}
                  radius={Math.max(14, zone.active_riders / 2.5)}
                  pathOptions={{
                    fillColor: color,
                    fillOpacity: isActive ? 0.85 : 0.55,
                    color: isActive ? '#fff' : color,
                    weight: isActive ? 2.5 : 1,
                  }}
                >
                  <LTooltip>
                    <div style={{ fontFamily: 'IBM Plex Mono', fontSize: 12, lineHeight: 1.6 }}>
                      <strong>{zone.zone_id}</strong><br />
                      Risk: {riskLabel(zone.risk_score)} ({(zone.risk_score * 100).toFixed(0)}%)<br />
                      Riders: {zone.active_riders}<br />
                      Triggers (30d): {zone.trigger_count_30d}<br />
                      {zone.last_trigger && <>Last: {zone.last_trigger}</>}
                      {isActive && <><br /><span style={{ color: '#EF4444', fontWeight: 700 }}>⚡ ACTIVE TRIGGER</span></>}
                    </div>
                  </LTooltip>
                  <Popup>
                    <div style={{ fontFamily: 'IBM Plex Mono', fontSize: 11, minWidth: 180 }}>
                      <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 6 }}>{zone.zone_id}</div>
                      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <tbody>
                          <tr><td style={{ color: '#666', paddingRight: 8 }}>City</td><td>{zone.city}</td></tr>
                          <tr><td style={{ color: '#666' }}>Risk score</td><td style={{ color: riskColor(zone.risk_score), fontWeight: 700 }}>{(zone.risk_score * 100).toFixed(0)}%</td></tr>
                          <tr><td style={{ color: '#666' }}>Active riders</td><td>{zone.active_riders}</td></tr>
                          <tr><td style={{ color: '#666' }}>Triggers (30d)</td><td>{zone.trigger_count_30d}</td></tr>
                          {zone.last_trigger && <tr><td style={{ color: '#666' }}>Last trigger</td><td>{zone.last_trigger}</td></tr>}
                          <tr><td style={{ color: '#666' }}>Centroid</td><td>{zone.centroid_lat.toFixed(4)}, {zone.centroid_lon.toFixed(4)}</td></tr>
                        </tbody>
                      </table>
                      {isActive && (
                        <div style={{ marginTop: 8, padding: '4px 8px', background: '#fef2f2', borderRadius: 4, color: '#dc2626', fontWeight: 700, fontSize: 11 }}>
                          ⚡ Active parametric trigger
                        </div>
                      )}
                    </div>
                  </Popup>
                </CircleMarker>
              )
            })}
            <CityLegend />
          </MapContainer>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div className="card">
            <div className="card-header">
              <div className="card-title">Zone Summary</div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {zones.slice().sort((a, b) => b.risk_score - a.risk_score).map(zone => (
                <div key={zone.zone_id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
                  <div style={{ width: 10, height: 10, borderRadius: '50%', background: riskColor(zone.risk_score), flexShrink: 0, boxShadow: activeZones.has(zone.zone_id) ? `0 0 0 3px ${riskColor(zone.risk_score)}40` : 'none' }} />
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 12, fontFamily: 'IBM Plex Mono', color: 'var(--text-1)' }}>{zone.zone_id}</div>
                    <div style={{ fontSize: 10, color: 'var(--text-3)' }}>{zone.active_riders} riders · T30d: {zone.trigger_count_30d}</div>
                  </div>
                  <div style={{ fontSize: 11, fontFamily: 'IBM Plex Mono', color: riskColor(zone.risk_score), fontWeight: 600 }}>
                    {(zone.risk_score * 100).toFixed(0)}%
                  </div>
                </div>
              ))}
            </div>
          </div>

          {activeTriggers.length > 0 && (
            <div className="card" style={{ borderColor: 'rgba(239,68,68,0.3)' }}>
              <div className="card-header">
                <div className="card-title">Active Triggers</div>
                <span className="badge badge-red">LIVE</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {activeTriggers.map((t, i) => (
                  <div key={i} style={{ padding: '8px 10px', background: 'var(--red-glow)', borderRadius: 6, border: '1px solid var(--red)', fontSize: 12 }}>
                    <div style={{ fontFamily: 'IBM Plex Mono', color: 'var(--red)', fontWeight: 700 }}>{t.zone}</div>
                    <div style={{ color: 'var(--text-2)', marginTop: 2 }}>{t.event_type.toUpperCase()} · {t.metric_value} · Tier {t.tier}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
