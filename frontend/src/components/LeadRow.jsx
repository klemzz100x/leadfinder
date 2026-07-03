import { useState } from 'react'
import { patchLead } from '../api.js'
import { googleMapsUrl } from '../utils.js'
import AddToListBtn from './AddToListBtn.jsx'

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

function normalizeWebsiteUrl(website) {
  return website.startsWith('http') ? website : `https://${website}`
}

function websiteHostname(website) {
  try {
    return new URL(normalizeWebsiteUrl(website)).hostname.replace(/^www\./, '')
  } catch {
    return website
  }
}

export default function LeadRow({ lead, onUpdate, lists, onListsChange, selected, onToggleSelect, creneau }) {
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

  // Un contact_status présent et différent du défaut "a_contacter" signifie
  // qu'un appel/contact a déjà été tenté sur ce lead (dans une liste, peu
  // importe laquelle) — mis en avant ici pour ne pas rappeler par erreur la
  // même entreprise depuis la vue Recherche.
  const alreadyContacted = lead.contact_status && lead.contact_status !== 'a_contacter'

  return (
    <>
      <div className={`lead-card temp-${lead.temperature}${alreadyContacted ? ' lead-card-contacted' : ''}`}>
        {/* Colonne 1 / Ligne 1 : case à cocher + badge température */}
        <div className="lead-card-badge">
          {onToggleSelect && (
            <input
              type="checkbox"
              className="lead-select-checkbox"
              checked={Boolean(selected)}
              onChange={() => onToggleSelect(lead.id)}
              title="Sélectionner ce lead"
            />
          )}
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

        {/* Colonne 3 / Ligne 1 : badge web + signaux Google Places */}
        <div className="lead-card-top-right">
          {alreadyContacted && (
            <span className="already-called-badge" title="Déjà contacté dans une liste — vérifier avant de rappeler">
              ☎️ Déjà appelé
            </span>
          )}
          <span className={`web-badge status-${lead.web_status}`}>
            {STATUS_LABEL[lead.web_status] || lead.web_status}
          </span>
          {lead.gmaps_website && (
            <span className="gmaps-badge gmaps-equipped" title={lead.gmaps_website}>
              ✅ Déjà équipé
            </span>
          )}
          {lead.gmaps_status === 'closed_permanently' && (
            <span className="gmaps-badge gmaps-closed">
              ⛔ Fermé définitivement
            </span>
          )}
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

          {lead.devis_suggere && (
            <span
              className="devis-suggere-badge"
              title="Prix indicatif basé sur note/avis Google et secteur — à ajuster au feeling pendant l'appel"
            >
              💰 {lead.devis_suggere.prix} € — {lead.devis_suggere.justification}
            </span>
          )}

          <div className="lead-contact">
            <span className="lead-phone">
              {lead.phone
                ? <a href={`tel:${lead.phone}`}>📞 {lead.phone}</a>
                : <span className="no-phone">Pas de tél.</span>
              }
            </span>
            {creneau && (
              <span
                className="creneau-highlight"
                title="Créneau indicatif, à ajuster selon retour terrain — n'empêche pas d'appeler en dehors"
              >
                🕐 Appeler entre {creneau}
              </span>
            )}
            {lead.website && (
              <a
                className="lead-website"
                href={normalizeWebsiteUrl(lead.website)}
                target="_blank"
                rel="noreferrer"
                title={lead.website}
              >
                🌐 {websiteHostname(lead.website)}
              </a>
            )}
          </div>
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
            {lead.notes?.trim() && <span className="btn-notes-badge">1</span>}
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
          <AddToListBtn
            lead={lead}
            lists={lists}
            onAdded={(list) => onListsChange?.(prev =>
              prev.map(l => l.id === list.id ? { ...l, lead_count: (l.lead_count || 0) + 1 } : l)
            )}
            onListCreated={(list) => onListsChange?.(prev => [list, ...prev])}
          />
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
