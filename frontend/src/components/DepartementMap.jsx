import { useEffect } from 'react'
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'

const FRANCE_CENTER = [46.6, 2.5]

function colorFor(chauds, max) {
  const ratio = max > 0 ? chauds / max : 0
  if (ratio > 0.66) return '#ef4444'
  if (ratio > 0.33) return '#f97316'
  return '#60a5fa'
}

function FlyToSelected({ selected, stats }) {
  const map = useMap()
  useEffect(() => {
    if (!selected) return
    const d = stats.find((s) => s.code === selected)
    if (d) map.flyTo([d.lat, d.lng], 8, { duration: 0.6 })
  }, [selected, stats, map])
  return null
}

export default function DepartementMap({ stats, selected, onSelect }) {
  const max = Math.max(1, ...stats.map((d) => d.chauds))

  return (
    <MapContainer center={FRANCE_CENTER} zoom={6} scrollWheelZoom className="dept-map">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FlyToSelected selected={selected} stats={stats} />
      {stats.map((d) => (
        <CircleMarker
          key={d.code}
          center={[d.lat, d.lng]}
          radius={8 + (d.chauds / max) * 18}
          pathOptions={{
            color: colorFor(d.chauds, max),
            fillColor: colorFor(d.chauds, max),
            fillOpacity: d.code === selected ? 0.9 : 0.55,
            weight: d.code === selected ? 3 : 1,
          }}
          eventHandlers={{ click: () => onSelect(d.code) }}
        >
          <Tooltip>{d.name} ({d.code}) — {d.chauds} chaud{d.chauds > 1 ? 's' : ''}</Tooltip>
        </CircleMarker>
      ))}
    </MapContainer>
  )
}
