import { useState } from 'react'
import { googleMapsUrl } from '../utils.js'
import { CONTACT_STATUS_COLOR } from '../statusColors.js'
import { USERS } from '../identity.js'
import CreneauButton from './CreneauButton.jsx'

export const STATUSES = [
  { value: 'a_contacter',   label: 'À contacter',   color: '#60a5fa' },
  { value: 'repondeur',     label: 'Répondeur',      color: '#eab308' },
  { value: 'rappel',        label: 'Rappel',         color: '#a78bfa' },
  { value: 'injoignable',   label: 'Injoignable',    color: CONTACT_STATUS_COLOR.injoignable },
  { value: 'pas_interesse', label: 'Pas intéressé',  color: CONTACT_STATUS_COLOR.pas_interesse },
  { value: 'devis_envoye',  label: 'Devis envoyé',   color: CONTACT_STATUS_COLOR.devis_envoye },
  { value: 'devis_relance', label: 'Devis relancé',  color: CONTACT_STATUS_COLOR.devis_relance },
  { value: 'closing',       label: 'Closing',        color: CONTACT_STATUS_COLOR.closing },
  { value: 'facture_payee', label: 'Facture payée',  color: CONTACT_STATUS_COLOR.facture_payee },
]

const STATUS_MAP = Object.fromEntries(STATUSES.map(s => [s.value, s]))

export default function ListLeadRow({ lead, onStatusChange, onRemove, onNotesChange, onBudgetChange, onAssignChange, creneau }) {
  const [showNotes, setShowNotes] = useState(false)
  const [notes, setNotes] = useState(lead.list_notes || '')
  const [saving, setSaving] = useState(false)
  const [budgetPropose, setBudgetPropose] = useState(lead.budget_propose ?? '')
  const [budgetFinal, setBudgetFinal] = useState(lead.budget_final ?? '')

  const meta = STATUS_MAP[lead.list_status] || STATUSES[0]
  const group = getGroup(lead.list_status)

  const handleStatus = async (e) => {
    setSaving(true)
    try { await onStatusChange(e.target.value) }
    finally { setSaving(false) }
  }

  const handleAssign = async (e) => {
    await onAssignChange?.(e.target.value)
  }

  const handleSaveNotes = async () => {
    await onNotesChange(notes)
    setShowNotes(false)
  }

  const handleBudgetBlur = (field, value) => {
    const num = value === '' ? null : Number(value)
    onBudgetChange?.({ [field]: num })
  }

  return (
    <>
      <div className="llr-row" style={{ borderLeftColor: meta.color }}>
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
          <CreneauButton creneau={creneau} businessType={lead.business_type} />
        </div>
        {(group === 'devis' || group === 'won') && (
          <div className="llr-budget-col">
            <input
              type="number"
              min="0"
              className="llr-budget-input"
              placeholder="Devisé €"
              title="Budget proposé"
              value={budgetPropose}
              onChange={(e) => setBudgetPropose(e.target.value)}
              onBlur={(e) => handleBudgetBlur('budget_propose', e.target.value)}
            />
            {group === 'won' && (
              <input
                type="number"
                min="0"
                className="llr-budget-input"
                placeholder="Final €"
                title="Budget final closé"
                value={budgetFinal}
                onChange={(e) => setBudgetFinal(e.target.value)}
                onBlur={(e) => handleBudgetBlur('budget_final', e.target.value)}
              />
            )}
          </div>
        )}
        <div className="llr-assign-col">
          <select
            className="llr-assign-select"
            value={lead.assigned_to || ''}
            onChange={handleAssign}
            title="Attribué à (visibilité partagée, pas un accès restreint)"
          >
            <option value="">— Non assigné</option>
            {USERS.map((u) => (
              <option key={u} value={u}>{u}</option>
            ))}
          </select>
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
          <a
            className="btn-notes"
            href={lead.gmaps_url || googleMapsUrl(lead)}
            target="_blank"
            rel="noreferrer"
            title="Voir sur Google Maps"
          >
            📍
          </a>
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
