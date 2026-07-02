import { useState, useEffect, useCallback } from 'react'
import { fetchRappels, patchListLead } from '../api.js'
import { STATUSES } from './ListLeadRow.jsx'
import { googleMapsUrl } from '../utils.js'

export default function RappelsView() {
  const [rappels, setRappels] = useState([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setRappels(await fetchRappels())
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  // Polling multi-utilisateurs : un rappel traité par l'un doit disparaître
  // de la todo-list de l'autre sans qu'il ait besoin de rafraîchir.
  useEffect(() => {
    const id = setInterval(load, 5000)
    return () => clearInterval(id)
  }, [load])

  const handleStatusChange = async (rappel, status) => {
    await patchListLead(rappel.list_id, rappel.id, { status })
    setRappels((prev) => prev.filter((r) => !(r.id === rappel.id && r.list_id === rappel.list_id)))
  }

  return (
    <div className="rappels-view">
      <div className="rappels-header">
        <h2>📞 Rappels à faire</h2>
        <span className="rappels-count">{rappels.length}</span>
      </div>

      {loading && <p className="empty">Chargement…</p>}
      {!loading && rappels.length === 0 && (
        <p className="empty">Aucun rappel en attente — tout est à jour 🎉</p>
      )}

      <div className="rappels-list">
        {rappels.map((r) => (
          <div key={`${r.list_id}-${r.id}`} className="rappel-card">
            <div className="rappel-main">
              <span className="rappel-name">{r.name}</span>
              <span className="rappel-meta">
                {r.business_type}{r.city ? ` · ${r.city}` : ''} · dans « {r.list_name} »
                {r.assigned_to ? ` · ${r.assigned_to}` : ''}
              </span>
              {r.list_notes && <span className="rappel-notes">{r.list_notes}</span>}
            </div>
            <div className="rappel-actions">
              {r.phone
                ? <a className="btn btn-sm" href={`tel:${r.phone}`}>📞 {r.phone}</a>
                : <span className="llr-no-phone">Pas de tél.</span>
              }
              <a
                className="btn-notes"
                href={r.gmaps_url || googleMapsUrl(r)}
                target="_blank"
                rel="noreferrer"
                title="Voir sur Google Maps"
              >
                📍
              </a>
              <select
                className="rappel-status-select"
                value="rappel"
                onChange={(e) => handleStatusChange(r, e.target.value)}
                title="Marquer comme traité"
              >
                {STATUSES.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
