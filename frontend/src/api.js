const BASE = '/api'

export async function scanCity(city) {
  const res = await fetch(`${BASE}/scan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ city }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function fetchLeads({ city, temperature, type } = {}) {
  const p = new URLSearchParams()
  if (city) p.set('city', city)
  if (temperature) p.set('temperature', temperature)
  if (type) p.set('type', type)
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
