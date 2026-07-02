export function googleMapsUrl(lead) {
  const query = [lead.name, lead.address || lead.city].filter(Boolean).join(', ')
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`
}

// /api/scan renvoie toujours une liste de résumés (un par zone scannée :
// une ville, ou un département). On les fusionne en un seul objet pour
// l'affichage (StatsBar attend un résumé unique).
export function mergeScanSummaries(summaries) {
  if (!summaries || summaries.length === 0) return null
  if (summaries.length === 1) return summaries[0]

  const merged = {
    city: summaries.map((s) => s.city).join(', '),
    total: 0,
    by_temperature: {},
    by_status: {},
    api_calls: 0,
    gmaps_checked: 0,
    duration_seconds: 0,
  }
  for (const s of summaries) {
    merged.total += s.total
    merged.api_calls += s.api_calls
    merged.gmaps_checked += s.gmaps_checked || 0
    merged.duration_seconds += s.duration_seconds
    for (const [k, v] of Object.entries(s.by_temperature || {})) {
      merged.by_temperature[k] = (merged.by_temperature[k] || 0) + v
    }
    for (const [k, v] of Object.entries(s.by_status || {})) {
      merged.by_status[k] = (merged.by_status[k] || 0) + v
    }
  }
  merged.duration_seconds = Math.round(merged.duration_seconds * 100) / 100
  return merged
}
