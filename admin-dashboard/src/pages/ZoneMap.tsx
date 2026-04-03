import React, { useEffect, useState } from 'react'
import { MapContainer, TileLayer, CircleMarker, Popup, Tooltip } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'

interface Zone {
  code: string
  city: string
  lat: number
  lng: number
  activeTriggers: number
  severity: 'none' | 'tier1' | 'tier2' | 'tier3'
  aqi?: number
  rainfall?: number
}

const ZONES: Zone[] = [
  { code: 'delhi_rohini', city: 'Delhi NCR', lat: 28.7495, lng: 77.0564, activeTriggers: 2, severity: 'tier2', aqi: 420 },
  { code: 'delhi_dwarka', city: 'Delhi NCR', lat: 28.5921, lng: 77.0460, activeTriggers: 1, severity: 'tier1', aqi: 340 },
  { code: 'delhi_saket', city: 'Delhi NCR', lat: 28.5244, lng: 77.2090, activeTriggers: 0, severity: 'none', aqi: 180 },
  { code: 'delhi_laxmi_nagar', city: 'Delhi NCR', lat: 28.6304, lng: 77.2772, activeTriggers: 1, severity: 'tier1', aqi: 310 },
  { code: 'mumbai_andheri', city: 'Mumbai', lat: 19.1136, lng: 72.8697, activeTriggers: 0, severity: 'none', rainfall: 12 },
  { code: 'mumbai_bandra', city: 'Mumbai', lat: 19.0596, lng: 72.8295, activeTriggers: 0, severity: 'none', rainfall: 8 },
  { code: 'mumbai_powai', city: 'Mumbai', lat: 19.1176, lng: 72.9060, activeTriggers: 1, severity: 'tier1', rainfall: 42 },
  { code: 'mumbai_dadar', city: 'Mumbai', lat: 19.0178, lng: 72.8478, activeTriggers: 0, severity: 'none', rainfall: 5 },
  { code: 'bengaluru_koramangala', city: 'Bengaluru', lat: 12.9352, lng: 77.6245, activeTriggers: 0, severity: 'none' },
  { code: 'bengaluru_whitefield', city: 'Bengaluru', lat: 12.9698, lng: 77.7500, activeTriggers: 0, severity: 'none' },
  { code: 'bengaluru_indiranagar', city: 'Bengaluru', lat: 12.9784, lng: 77.6408, activeTriggers: 0, severity: 'none' },
  { code: 'hyderabad_gachibowli', city: 'Hyderabad', lat: 17.4401, lng: 78.3489, activeTriggers: 0, severity: 'none' },
  { code: 'hyderabad_hitech_city', city: 'Hyderabad', lat: 17.4435, lng: 78.3772, activeTriggers: 0, severity: 'none' },
  { code: 'hyderabad_secunderabad', city: 'Hyderabad', lat: 17.4399, lng: 78.4983, activeTriggers: 0, severity: 'none' },
  { code: 'pune_kothrud', city: 'Pune', lat: 18.5074, lng: 73.8077, activeTriggers: 0, severity: 'none' },
  { code: 'pune_hinjewadi', city: 'Pune', lat: 18.5912, lng: 73.7390, activeTriggers: 0, severity: 'none' },
  { code: 'pune_viman_nagar', city: 'Pune', lat: 18.5679, lng: 73.9143, activeTriggers: 0, severity: 'none' },
  { code: 'kolkata_salt_lake', city: 'Kolkata', lat: 22.5803, lng: 88.4161, activeTriggers: 0, severity: 'none' },
  { code: 'kolkata_newtown', city: 'Kolkata', lat: 22.5923, lng: 88.4767, activeTriggers: 0, severity: 'none' },
  { code: 'kolkata_park_street', city: 'Kolkata', lat: 22.5513, lng: 88.3527, activeTriggers: 1, severity: 'tier1', aqi: 305 },
  { code: 'kolkata_howrah', city: 'Kolkata', lat: 22.5958, lng: 88.2636, activeTriggers: 0, severity: 'none' },
]

const SEVERITY_COLORS = {
  none: '#5A7090',
  tier1: '#4CAF50',
  tier2: '#FF9800',
  tier3: '#F44336',
}

const SEVERITY_RADIUS = {
  none: 8,
  tier1: 12,
  tier2: 16,
  tier3: 20,
}

export default function ZoneMap() {
  const [zones] = useState<Zone[]>(ZONES)
  const activeCount = zones.filter(z => z.activeTriggers > 0).length
  const totalRiders = 847

  return (
    <div>
      <div className="page-header">
        <h2>Live Zone Map</h2>
        <p>Real-time trigger status across 21 zones in 6 cities</p>
      </div>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-value">{zones.length}</div>
          <div className="stat-label">Total Zones</div>
        </div>
        <div className="stat-card">
          <div className="stat-value" style={{ color: activeCount > 0 ? '#FF9800' : undefined }}>{activeCount}</div>
          <div className="stat-label">Active Triggers</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{totalRiders}</div>
          <div className="stat-label">Enrolled Riders</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">6</div>
          <div className="stat-label">Cities Covered</div>
        </div>
      </div>

      <div className="map-container">
        <MapContainer
          center={[22.0, 78.0]}
          zoom={5}
          style={{ height: '100%', width: '100%', background: '#0A1628' }}
          scrollWheelZoom={true}
        >
          <TileLayer
            attribution='&copy; OpenStreetMap'
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          />
          {zones.map((zone) => (
            <CircleMarker
              key={zone.code}
              center={[zone.lat, zone.lng]}
              radius={SEVERITY_RADIUS[zone.severity]}
              pathOptions={{
                color: SEVERITY_COLORS[zone.severity],
                fillColor: SEVERITY_COLORS[zone.severity],
                fillOpacity: zone.severity === 'none' ? 0.3 : 0.6,
                weight: 2,
              }}
            >
              <Tooltip direction="top" offset={[0, -10]}>
                <div style={{ fontFamily: 'Inter', fontSize: 12 }}>
                  <strong>{zone.code.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</strong>
                  <br />
                  {zone.city} • {zone.activeTriggers > 0 ? `${zone.activeTriggers} active trigger(s)` : 'No triggers'}
                  {zone.aqi && <><br />AQI: {zone.aqi}</>}
                  {zone.rainfall && <><br />Rain: {zone.rainfall}mm</>}
                </div>
              </Tooltip>
              <Popup>
                <div style={{ fontFamily: 'Inter', minWidth: 200 }}>
                  <h3 style={{ margin: '0 0 8px', fontSize: 14 }}>{zone.code}</h3>
                  <p style={{ margin: '4px 0', fontSize: 12 }}>City: {zone.city}</p>
                  <p style={{ margin: '4px 0', fontSize: 12 }}>Active Triggers: {zone.activeTriggers}</p>
                  <p style={{ margin: '4px 0', fontSize: 12 }}>
                    Severity: <span style={{ color: SEVERITY_COLORS[zone.severity], fontWeight: 600 }}>
                      {zone.severity === 'none' ? 'Clear' : zone.severity.toUpperCase()}
                    </span>
                  </p>
                  {zone.aqi && <p style={{ margin: '4px 0', fontSize: 12 }}>AQI: {zone.aqi}</p>}
                  {zone.rainfall && <p style={{ margin: '4px 0', fontSize: 12 }}>Rainfall: {zone.rainfall}mm</p>}
                </div>
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>
    </div>
  )
}
