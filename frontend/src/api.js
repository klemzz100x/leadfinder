const BASE = '/api'

// Scanne une ville, ou (sans ville) un ou plusieurs départements entiers.
// Renvoie toujours une liste de résumés (un par zone scannée) — cf. mergeScanSummaries().
export async function scanArea({ city, departements, scannedBy } = {}) {
  const res = await fetch(`${BASE}/scan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      city: city || null,
      departements: departements?.length ? departements : null,
      scanned_by: scannedBy || null,
    }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function fetchLeads({ city, temperature, type, showEquipped, showClosed, departements } = {}) {
  const p = new URLSearchParams()
  if (city) p.set('city', city)
  if (temperature) p.set('temperature', temperature)
  if (type) p.set('type', type)
  if (showEquipped) p.set('show_equipped', 'true')
  if (showClosed) p.set('show_closed', 'true')
  for (const d of departements || []) p.append('departements', d)
  const res = await fetch(`${BASE}/leads?${p}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function fetchMeta(city) {
  const p = new URLSearchParams()
  if (city) p.set('city', city)
  const res = await fetch(`${BASE}/leads/meta?${p}`)
  if (!res.ok) return { cities: [], types: [] }
  return res.json()
}

// business_type bruts (non groupés en catégories) — utilisé uniquement par
// l'éditeur de catégories, qui a besoin des valeurs brutes à assigner.
// fetchMeta() renvoie des catégories déjà groupées, impropres à cet usage.
export async function fetchRawTypes() {
  const res = await fetch(`${BASE}/leads/meta/raw-types`)
  if (!res.ok) return []
  const data = await res.json()
  return data.types || []
}

export async function fetchDepartements() {
  const res = await fetch(`${BASE}/departements`)
  if (!res.ok) return []
  return res.json()
}

export async function fetchDepartementEstimate(code) {
  const res = await fetch(`${BASE}/departements/${encodeURIComponent(code)}/estimate`)
  if (!res.ok) return null
  return res.json()
}

export async function patchLead(id, data) {
  const res = await fetch(`${BASE}/leads/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function suggestCities(q) {
  if (!q || q.length < 2) return []
  const res = await fetch(`${BASE}/cities/suggest?q=${encodeURIComponent(q)}`)
  if (!res.ok) return []
  return res.json()
}

export function exportCsvUrl(city) {
  return city ? `${BASE}/export?city=${encodeURIComponent(city)}` : `${BASE}/export`
}

export async function fetchCategories() {
  const res = await fetch(`${BASE}/categories`)
  if (!res.ok) return {}
  return res.json()
}

export async function saveCategories(categories) {
  const res = await fetch(`${BASE}/categories`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ categories }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function fetchCreneaux() {
  const res = await fetch(`${BASE}/creneaux`)
  if (!res.ok) return {}
  return res.json()
}

export async function saveCreneaux(familles) {
  const res = await fetch(`${BASE}/creneaux`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ familles }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function fetchCreneauxMap() {
  const res = await fetch(`${BASE}/creneaux/map`)
  if (!res.ok) return {}
  return res.json()
}

export async function fetchLists() {
  const res = await fetch(`${BASE}/lists`)
  if (!res.ok) return []
  return res.json()
}

export async function fetchRappels() {
  const res = await fetch(`${BASE}/rappels`)
  if (!res.ok) return []
  return res.json()
}

export async function fetchDevisARelancer() {
  const res = await fetch(`${BASE}/devis-a-relancer`)
  if (!res.ok) return []
  return res.json()
}

export async function createList(name) {
  const res = await fetch(`${BASE}/lists`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function deleteList(id) {
  const res = await fetch(`${BASE}/lists/${encodeURIComponent(id)}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function renameList(id, name) {
  return patchList(id, { name })
}

export async function patchList(id, data) {
  const res = await fetch(`${BASE}/lists/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function fetchListLeads(listId) {
  const res = await fetch(`${BASE}/lists/${encodeURIComponent(listId)}/leads`)
  if (!res.ok) return []
  return res.json()
}

export async function fetchListStats(listId) {
  const res = await fetch(`${BASE}/lists/${encodeURIComponent(listId)}/stats`)
  if (!res.ok) return null
  return res.json()
}

export async function addLeadsToList(listId, leadIds) {
  const res = await fetch(`${BASE}/lists/${encodeURIComponent(listId)}/leads`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lead_ids: leadIds }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function removeLeadFromList(listId, leadId) {
  const res = await fetch(`${BASE}/lists/${encodeURIComponent(listId)}/leads/${encodeURIComponent(leadId)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function fetchDeptStats(activite) {
  const p = new URLSearchParams()
  if (activite) p.set('activite', activite)
  const res = await fetch(`${BASE}/stats/departements?${p}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function fetchVilleStats(activite, departements) {
  const p = new URLSearchParams()
  if (activite) p.set('activite', activite)
  for (const d of departements || []) p.append('departements', d)
  const res = await fetch(`${BASE}/stats/villes?${p}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function fetchLeadsInBounds({ activite, bounds, limit = 300 } = {}) {
  const p = new URLSearchParams()
  if (activite) p.set('activite', activite)
  p.set('south', bounds.south)
  p.set('west', bounds.west)
  p.set('north', bounds.north)
  p.set('east', bounds.east)
  p.set('limit', limit)
  const res = await fetch(`${BASE}/leads/geo?${p}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function fetchDashboard(month) {
  const p = new URLSearchParams()
  if (month) p.set('month', month)
  const res = await fetch(`${BASE}/dashboard?${p}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function fetchPerformance(period) {
  const p = new URLSearchParams({ period: period || 'day' })
  const res = await fetch(`${BASE}/performance?${p}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function sendLeads(leadIds, preview = true) {
  const res = await fetch(`${BASE}/leads/send`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lead_ids: leadIds, preview }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function patchListLead(listId, leadId, data) {
  const res = await fetch(`${BASE}/lists/${encodeURIComponent(listId)}/leads/${encodeURIComponent(leadId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
