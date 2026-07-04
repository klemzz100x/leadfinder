import { useState, useEffect } from 'react'
import { sendLeads } from '../api.js'

// Aperçu obligatoire avant tout envoi réel : à l'ouverture, génère le site +
// le devis + compose l'email pour chaque lead en mode preview (aucun email
// n'est envoyé à ce stade). L'utilisateur relit, puis confirme explicitement
// pour déclencher l'envoi réel — garde-fou demandé pour ne jamais expédier
// un site/email mal généré à un vrai prospect par erreur.
export default function SendPreviewModal({ leadIds, onClose, onSent }) {
  const [loading, setLoading] = useState(true)
  const [results, setResults] = useState([])
  const [sending, setSending] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [expanded, setExpanded] = useState(() => new Set())

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    sendLeads(leadIds, true)
      .then((data) => { if (!cancelled) setResults(data) })
      .catch((e) => { if (!cancelled) setLoadError(e.message) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [leadIds])

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget && !sending) onClose()
  }

  const toggleExpand = (leadId) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(leadId)) next.delete(leadId)
      else next.add(leadId)
      return next
    })
  }

  const okResults = results.filter((r) => r.ok)

  const handleConfirmSend = async () => {
    if (okResults.length === 0) return
    if (!confirm(`Envoyer réellement l'email à ${okResults.length} prospect(s) ? Cette action ne peut pas être annulée.`)) {
      return
    }
    setSending(true)
    try {
      await sendLeads(okResults.map((r) => r.lead_id), false)
      onSent()
    } catch (e) {
      setLoadError(e.message)
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={handleOverlayClick}>
      <div className="modal-panel send-preview-panel" role="dialog" aria-modal="true" aria-label="Aperçu avant envoi">
        <div className="modal-header">
          <h2>✉️ Aperçu avant envoi ({leadIds.length} lead{leadIds.length > 1 ? 's' : ''})</h2>
          <button className="modal-close" onClick={onClose} title="Fermer" disabled={sending}>✕</button>
        </div>

        <div className="modal-body">
          {loading && <p className="send-preview-hint">Génération des sites, devis et emails en cours… (peut prendre jusqu'à une minute par lead)</p>}
          {loadError && <p className="send-preview-error">{loadError}</p>}

          {!loading && results.map((r) => (
            <div key={r.lead_id} className={`send-preview-card${r.ok ? '' : ' send-preview-card-error'}`}>
              <div className="send-preview-card-header">
                <strong>{r.name}</strong>
                {r.ok ? <span className="send-preview-ok">✓ prêt</span> : <span className="send-preview-ko">✗ échec</span>}
              </div>

              {!r.ok && <p className="send-preview-error">{r.error}</p>}

              {r.ok && (
                <>
                  <p className="send-preview-links">
                    <a href={r.site_url} target="_blank" rel="noreferrer">🔗 Voir le site</a>
                    {' · '}
                    <span>📄 {r.devis_numero}</span>
                  </p>
                  <p className="send-preview-links">
                    À : {r.email.to} — Objet : {r.email.subject}
                  </p>
                  <button className="btn btn-sm" onClick={() => toggleExpand(r.lead_id)}>
                    {expanded.has(r.lead_id) ? 'Masquer l\'email' : 'Voir l\'email complet'}
                  </button>
                  {expanded.has(r.lead_id) && (
                    <iframe
                      className="send-preview-email-frame"
                      srcDoc={r.email.html_body}
                      title={`Aperçu email — ${r.name}`}
                    />
                  )}
                </>
              )}
            </div>
          ))}
        </div>

        <div className="modal-footer">
          <button className="btn btn-cancel" onClick={onClose} disabled={sending}>Annuler</button>
          <button
            className="btn btn-primary"
            onClick={handleConfirmSend}
            disabled={loading || sending || okResults.length === 0}
          >
            {sending ? 'Envoi en cours…' : `Confirmer et envoyer (${okResults.length})`}
          </button>
        </div>
      </div>
    </div>
  )
}
