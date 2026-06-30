import { useState } from 'react'

export const STATUSES = [
  { value: 'a_contacter',   label: 'À contacter',   color: '#60a5fa' },
  { value: 'repondeur',     label: 'Répondeur',      color: '#eab308' },
  { value: 'rappel',        label: 'Rappel',         color: '#a78bfa' },
  { value: 'injoignable',   label: 'Injoignable',    color: '#6b7280' },
  { value: 'pas_interesse', label: 'Pas intéressé',  color: '#ef4444' },
  { value: 'devis_envoye',  label: 'Devis envoyé',   color: '#f97316' },
  { value: 'devis_relance', label: 'Devis relancé',  color: '#fb923c' },
  { value: 'closing',       label: 'Closing',        color: '#22c55e' },
  { value: 'facture_payee', label: 'Facture payée',  color: '#10b981' },
]

const STATUS_MAP = Object.fromEntries(STATUSES.map(s => [s.value, s]))

export default function ListLeadRow({ lead, onStatusChange, onRemove, onNotesChange }) {
  const [showNotes, setShowNotes] = useState(false)
  const [notes, setNotes] = useState(lead.list_notes || '')
  const [saving, setSaving] = useState(false)

  const meta = STATUS_MAP[lead.list_status] || STATUSES[0]

  const handleStatus = async (e) => {
    setSaving(true)
    try { await onStatusChange(e.target.value) }
    finally { setSaving(false) }
  }

  const handleSaveNotes = async () => {
    await onNotesChange(notes)
    setShowNotes(false)
  }

  return (
    <>
      <div className={`llr-row status-group-${getGroup(lead.list_status)}`}>
        <div className="llr-info">
          <span className="llr-name" title={lead.address || lead.name}>{lead.name}</span>
          <span className="llr-meta">{lead.business_type}{lead.city ? ` · ${lead.city}` : ''}</span>
          {lead.list_notes && <span className="llr-note-preview">{lead.list_notes}</span>}
        </div>
        <div className="llr-phone">
          {lead.phone
            ? <a href={`tel:${lead.phone}`}>📞 {lead.phone}</a>
            : <span className="llr-no-phone">Pas de tél.</span>
          }
        </div>
        <div className="llr-status-col">
          <select
            className="status-select"
            value={lead.list_status}
            onChange={handleStatus}
            disabled={saving}
            style={{ color: meta.color, borderColor: meta.color + '60' }}
          >
            {STATUSES.map(s => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </div>
        <div className="llr-actions">
          <button
            className={`btn-notes${showNotes ? ' active' : ''}`}
            onClick={() => setShowNotes(v => !v)}
            title="Notes"
          >
            📝
          </button>
          <button className="llr-btn-remove" onClick={onRemove} title="Retirer de la liste">✕</button>
        </div>
      </div>
      {showNotes && (
        <div className="llr-notes-panel">
          <textarea
            value={notes}
            onChange={e => setNotes(e.target.value)}
            rows={2}
            placeholder="Notes sur ce prospect…"
          />
          <div className="llr-notes-actions">
            <button className="btn btn-sm" onClick={handleSaveNotes}>Enregistrer</button>
            <button className="btn btn-sm btn-cancel" onClick={() => setShowNotes(false)}>Annuler</button>
          </div>
        </div>
      )}
    </>
  )
}

function getGroup(status) {
  if (['closing', 'facture_payee'].includes(status)) return 'won'
  if (['pas_interesse', 'injoignable'].includes(status)) return 'lost'
  if (['devis_envoye', 'devis_relance'].includes(status)) return 'devis'
  return 'pipeline'
}
