import { useState } from 'react'
import { patchLead } from '../api.js'

const TEMP_ICON  = { chaud: '🔥', tiede: '🟠', froid: '❄️', a_verifier: '❓' }
const TEMP_LABEL = { chaud: 'Chaud', tiede: 'Tiède', froid: 'Froid', a_verifier: 'À vérifier' }

const STATUS_LABEL = {
  NO_SITE: 'Aucun site',
  SOCIAL_ONLY: 'Réseau social',
  AGGREGATOR: 'Agrégateur',
  FREE_BUILDER: 'Site gratuit',
  REAL_SITE_POOR: 'Site faible',
  REAL_SITE_OK: 'Site OK',
  UNVERIFIED: 'Inconnu',
}

export default function LeadRow({ lead, onUpdate }) {
  const [called, setCalled]       = useState(Boolean(lead.called))
  const [saving, setSaving]       = useState(false)
  const [showNotes, setShowNotes] = useState(false)
  const [notes, setNotes]         = useState(lead.notes || '')

  const toggleCalled = async () => {
    const next = !called
    setSaving(true)
    try {
      await patchLead(lead.id, { called: next })
      setCalled(next)
      onUpdate({ id: lead.id, called: next })
    } finally {
      setSaving(false)
    }
  }

  const saveNotes = async () => {
    await patchLead(lead.id, { notes })
    setShowNotes(false)
    onUpdate({ id: lead.id, notes })
  }

  const scorePercent = Math.min(Math.max(lead.score, 0), 1) * 100

  return (
    <>
      <div className={`lead-card temp-${lead.temperature}`}>
        {/* Colonne 1 / Ligne 1 : badge température */}
        <div className="lead-card-badge">
          <span className={`temp-pill temp-${lead.temperature}`}>
            {TEMP_ICON[lead.temperature] || '?'}{' '}
            {TEMP_LABEL[lead.temperature] || lead.temperature}
          </span>
        </div>

        {/* Colonne 2 / Ligne 1 : nom + type */}
        <div className="lead-card-main">
          <span className="lead-name" title={lead.address || lead.name}>
            {lead.name}
          </span>
          <span className="lead-type">{lead.business_type}</span>
        </div>

        {/* Colonne 3 / Ligne 1 : badge web */}
        <div className="lead-card-top-right">
          <span className={`web-badge status-${lead.web_status}`}>
            {STATUS_LABEL[lead.web_status] || lead.web_status}
          </span>
        </div>

        {/* Colonne 1-2 / Ligne 2 : score + téléphone */}
        <div className="lead-card-score-col">
          <div className="score-section">
            <span className="score-label">Score</span>
            <div className="score-track">
              <div
                className={`score-fill temp-${lead.temperature}`}
                style={{ width: `${scorePercent}%` }}
              />
            </div>
            <span className="score-value">{lead.score.toFixed(2)}</span>
          </div>

          <span className="lead-phone">
            {lead.phone
              ? <a href={`tel:${lead.phone}`}>📞 {lead.phone}</a>
              : <span className="no-phone">Pas de tél.</span>
            }
          </span>
        </div>

        {/* Colonne 3 / Ligne 2 : actions */}
        <div className="lead-card-actions-col">
          <button
            className={`btn-call${called ? ' called' : ''}`}
            onClick={toggleCalled}
            disabled={saving}
            title={called ? 'Marquer non appelé' : 'Appeler ce lead'}
          >
            {called ? '✓ Appelé' : '📞 Appeler'}
          </button>
          <button
            className="btn-notes"
            onClick={() => setShowNotes(v => !v)}
            title="Notes"
          >
            📝
          </button>
        </div>
      </div>

      {showNotes && (
        <div className="lead-notes-panel">
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Notes sur cet appel…"
            rows={2}
          />
          <button className="btn btn-sm" onClick={saveNotes}>Enregistrer</button>
          <button className="btn btn-sm btn-cancel" onClick={() => setShowNotes(false)}>Annuler</button>
          {lead.website
            ? (
              <a className="btn btn-sm" href={lead.website} target="_blank" rel="noreferrer">
                Voir le site
              </a>
            ) : (
              <a
                className="btn btn-sm"
                href={`https://www.google.com/search?q=${encodeURIComponent(lead.name + ' ' + (lead.city || ''))}`}
                target="_blank"
                rel="noreferrer"
              >
                Rechercher
              </a>
            )
          }
        </div>
      )}
    </>
  )
}
