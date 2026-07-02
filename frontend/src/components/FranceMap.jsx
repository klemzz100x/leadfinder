import { useEffect, useRef, useState } from 'react'
import { CircleMarker, MapContainer, Marker, Popup, TileLayer, Tooltip, useMap, useMapEvents } from 'react-leaflet'
import MarkerClusterGroup from 'react-leaflet-cluster'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { fetchLeadsInBounds } from '../api.js'
import LeadMapPopup from './LeadMapPopup.jsx'
import { CONTACT_STATUS_COLOR, CONTACT_STATUS_LABEL } from '../statusColors.js'

const FRANCE_CENTER = [46.6, 2.5]
const FRANCE_ZOOM = 6
// Zoom à partir duquel on bascule des bulles ville vers les marqueurs précis.
const DRILL_ZOOM = 12
const VIEWPORT_DEBOUNCE_MS = 300

const TEMP_COLOR = { chaud: '#ef4444', tiede: '#f97316', froid: '#9ca3af', a_verifier: '#eab308' }

function colorForRatio(count, max) {
  const ratio = max > 0 ? count / max : 0
  if (ratio > 0.66) return '#ef4444'
  if (ratio > 0.33) return '#f97316'
  return '#60a5fa'
}

function cityIcon(chauds, max) {
  const size = Math.round(28 + (chauds / max) * 24)
  return L.divIcon({
    html: `<div class="city-bubble" style="width:${size}px;height:${size}px;background:${colorForRatio(chauds, max)};">${chauds}</div>`,
    className: 'city-bubble-wrap',
    iconSize: [size, size],
  })
}

// Le cluster additionne les leads chauds des villes qu'il regroupe (pas juste
// leur nombre) pour afficher un vrai total, comme demandé.
function clusterIcon(cluster) {
  const markers = cluster.getAllChildMarkers()
  const total = markers.reduce((sum, m) => sum + (typeof m.options.chauds === 'number' ? m.options.chauds : 0), 0)
    || cluster.getChildCount()
  const maxSingle = Math.max(1, ...markers.map((m) => m.options.chauds || 0))
  const size = Math.min(70, 32 + Math.round(Math.sqrt(total) * 6))
  return L.divIcon({
    html: `<div class="city-bubble city-cluster-bubble" style="width:${size}px;height:${size}px;background:${colorForRatio(total, Math.max(total, maxSingle))};">${total}</div>`,
    className: 'city-bubble-wrap',
    iconSize: [size, size],
  })
}

// Légende du code couleur des marqueurs précis (niveau micro uniquement —
// les bulles ville/cluster du niveau macro restent sur la densité de leads
// chauds, sans rapport avec le statut de contact individuel).
function MicroLegend() {
  const entries = [
    { color: TEMP_COLOR.chaud, label: 'Chaud (non traité)' },
    ...Object.entries(CONTACT_STATUS_LABEL)
      .filter(([status]) => ['injoignable', 'pas_interesse', 'devis_envoye', 'closing'].includes(status))
      .map(([status, label]) => ({ color: CONTACT_STATUS_COLOR[status], label })),
  ]
  return (
    <div className="map-legend">
      {entries.map((e) => (
        <div key={e.label} className="map-legend-item">
          <span className="map-legend-dot" style={{ background: e.color }} />
          {e.label}
        </div>
      ))}
    </div>
  )
}

function BackToFranceButton() {
  const map = useMap()
  return (
    <button
      type="button"
      className="map-back-btn"
      onClick={() => map.flyTo(FRANCE_CENTER, FRANCE_ZOOM, { duration: 0.8 })}
    >
      🇫🇷 Retour vue France
    </button>
  )
}

function FlyToVille({ selectedVille, villeStats }) {
  const map = useMap()
  useEffect(() => {
    if (!selectedVille) return
    const v = villeStats.find((s) => s.name === selectedVille)
    if (v) map.flyTo([v.lat, v.lng], DRILL_ZOOM + 1, { duration: 0.6 })
  }, [selectedVille, villeStats, map])
  return null
}

// Écoute le zoom/déplacement de la carte et bascule vers le niveau 2 (marqueurs
// précis, requête bornée au viewport) une fois le seuil DRILL_ZOOM franchi.
function ZoomWatcher({ onViewportChange }) {
  const debounceRef = useRef(null)

  const evaluate = (map) => {
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      const zoom = map.getZoom()
      if (zoom >= DRILL_ZOOM) {
        const b = map.getBounds()
        onViewportChange({
          drilledIn: true,
          bounds: { south: b.getSouth(), west: b.getWest(), north: b.getNorth(), east: b.getEast() },
        })
      } else {
        onViewportChange({ drilledIn: false, bounds: null })
      }
    }, VIEWPORT_DEBOUNCE_MS)
  }

  const map = useMapEvents({
    moveend: () => evaluate(map),
    zoomend: () => evaluate(map),
  })

  return null
}

export default function FranceMap({ villeStats, activite, selectedVille, onSelectVille, lists, onListsChange }) {
  const [viewport, setViewport] = useState({ drilledIn: false, bounds: null })
  const [preciseLeads, setPreciseLeads] = useState([])
  // Distinct de `preciseLeads.length > 0` : une zone dézoomée-puis-zoomée peut
  // légitimement n'avoir aucun lead chaud. Sans ce flag, les bulles macro
  // disparaissent dès le franchissement du zoom (rendu conditionnel sur
  // `drilledIn`) alors que le fetch des marqueurs précis est encore en vol —
  // trou visuel où plus rien n'est affiché, qui ressemble à des leads qui
  // disparaissent. On garde les bulles jusqu'à ce que le premier fetch de la
  // session "zoomée" ait abouti, puis on bascule proprement.
  const [preciseReady, setPreciseReady] = useState(false)

  const maxChauds = Math.max(1, ...villeStats.map((v) => v.chauds))

  useEffect(() => {
    if (!viewport.drilledIn || !viewport.bounds) {
      setPreciseLeads([])
      setPreciseReady(false)
      return
    }
    let cancelled = false
    fetchLeadsInBounds({ activite, bounds: viewport.bounds })
      .then((data) => { if (!cancelled) { setPreciseLeads(data); setPreciseReady(true) } })
      .catch(() => { if (!cancelled) { setPreciseLeads([]); setPreciseReady(true) } })
    return () => { cancelled = true }
  }, [viewport, activite])

  const showBubbles = !viewport.drilledIn || !preciseReady
  const showPrecise = viewport.drilledIn && preciseReady

  return (
    <MapContainer center={FRANCE_CENTER} zoom={FRANCE_ZOOM} scrollWheelZoom className="dept-map">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <ZoomWatcher onViewportChange={setViewport} />
      <FlyToVille selectedVille={selectedVille} villeStats={villeStats} />
      <BackToFranceButton />
      {showPrecise && <MicroLegend />}

      {showBubbles && (
        <MarkerClusterGroup iconCreateFunction={clusterIcon} showCoverageOnHover={false}>
          {villeStats.map((v) => (
            <Marker
              key={v.name}
              position={[v.lat, v.lng]}
              icon={cityIcon(v.chauds, maxChauds)}
              chauds={v.chauds}
              eventHandlers={{ click: () => onSelectVille(v.name) }}
            >
              <Tooltip>{v.name} — {v.chauds} chaud{v.chauds > 1 ? 's' : ''}</Tooltip>
            </Marker>
          ))}
        </MarkerClusterGroup>
      )}

      {showPrecise && preciseLeads.map((lead) => {
        // Un point reste rouge (chaud, non traité) tant qu'aucun contact n'a
        // été enregistré dans une liste, puis prend la couleur du statut le
        // plus avancé une fois traité (ex: vert une fois "devis fait").
        const color = CONTACT_STATUS_COLOR[lead.contact_status] || TEMP_COLOR[lead.temperature] || '#60a5fa'
        return (
        <CircleMarker
          key={lead.id}
          center={[lead.lat, lead.lng]}
          radius={9}
          pathOptions={{
            color,
            fillColor: color,
            fillOpacity: 0.85,
            weight: 2,
          }}
        >
          <Tooltip>{lead.name}</Tooltip>
          <Popup minWidth={240}>
            <LeadMapPopup lead={lead} lists={lists} onListsChange={onListsChange} />
          </Popup>
        </CircleMarker>
        )
      })}
    </MapContainer>
  )
}
