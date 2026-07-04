import { useState, useEffect, useCallback } from 'react'
import { fetchDevisARelancer, patchListLead } from '../api.js'
import { googleMapsUrl } from '../utils.js'

function joursDepuis(iso) {
  const jours = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000)
  if (jours <= 0) return "Envoyé aujourd'hui"
  if (jours === 1) return 'Envoyé hier'
  return `Envoyé il y a ${jours} jours`
}

// Urgence de relance croissante avec l'ancienneté — cadence habituelle d'un
// devis (relance sous 1-2 semaines) : vert = envoyé récemment, orange = à
// relancer bientôt, rouge = en attente depuis longtemps, prioritaire.
function urgenceRelance(iso) {
  const jours = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000)
  if (jours >= 14) return 'urgent'
  if (jours >= 7) return 'attention'
  return 'recent'
}

function dateFr(iso) {
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' })
}

export default function DevisRelanceView() {
  const [devis, setDevis] = useState([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setDevis(await fetchDevisARelancer())
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  // Polling multi-utilisateurs, même logique que RappelsView.
  useEffect(() => {
    const id = setInterval(load, 5000)
    return () => clearInterval(id)
  }, [load])

  // "Négociation" relance simplement la date (reste dans la todo-list) ;
  // "Approuvé"/"Rejeté" posent le statut pipeline correspondant et effacent
  // devis_envoye_le (sort de la todo-list, devenue sans objet une fois l'issue connue).
  const handleStatutDevis = async (d, choix) => {
    if (choix === 'negociation') {
      await patchListLead(d.list_id, d.id, { status: 'devis_relance', devis_envoye: true })
      setDevis((prev) => prev.map((x) => (x.id === d.id && x.list_id === d.list_id)
        ? { ...x, status: 'devis_relance', devis_envoye_le: new Date().toISOString() }
        : x))
      return
    }
    const status = choix === 'approuve' ? 'closing' : 'pas_interesse'
    await patchListLead(d.list_id, d.id, { status, devis_envoye: false })
    setDevis((prev) => prev.filter((x) => !(x.id === d.id && x.list_id === d.list_id)))
  }

  const handleRetirer = async (d) => {
    await patchListLead(d.list_id, d.id, { devis_envoye: false })
    setDevis((prev) => prev.filter((x) => !(x.id === d.id && x.list_id === d.list_id)))
  }

  return (
    <div className="rappels-view">
      <div className="rappels-header">
        <h2>📨 Devis à relancer</h2>
        <span className="rappels-count">{devis.length}</span>
      </div>

      {loading && <p className="empty">Chargement…</p>}
      {!loading && devis.length === 0 && (
        <p className="empty">Aucun devis envoyé en attente de relance 🎉</p>
      )}

      <div className="rappels-list">
        {devis.map((d) => (
          <div key={`${d.list_id}-${d.id}`} className="rappel-card">
            <div className="rappel-main">
              <div className="rappel-name-row">
                <span className="rappel-name">{d.name}</span>
                <span
                  className={`rappel-devis-date rappel-devis-date-${urgenceRelance(d.devis_envoye_le)}`}
                  title={`Devis envoyé le ${dateFr(d.devis_envoye_le)}`}
                >
                  📅 {dateFr(d.devis_envoye_le)} · {joursDepuis(d.devis_envoye_le)}
                </span>
              </div>
              <span className="rappel-meta">
                {d.business_type}{d.city ? ` · ${d.city}` : ''} · dans « {d.list_name} »
                {d.assigned_to ? ` · ${d.assigned_to}` : ''}
                {d.budget_propose ? ` · ${Math.round(d.budget_propose).toLocaleString('fr-FR')} €` : ''}
              </span>
              {d.list_notes && <span className="rappel-notes">{d.list_notes}</span>}
            </div>
            <div className="rappel-actions">
              {d.phone
                ? <a className="btn btn-sm" href={`tel:${d.phone}`}>📞 {d.phone}</a>
                : <span className="llr-no-phone">Pas de tél.</span>
              }
              <a
                className="btn-notes"
                href={d.gmaps_url || googleMapsUrl(d)}
                target="_blank"
                rel="noreferrer"
                title="Voir sur Google Maps"
              >
                📍
              </a>
              <select
                className="rappel-statut-select"
                defaultValue=""
                onChange={(e) => { const v = e.target.value; e.target.value = ''; handleStatutDevis(d, v) }}
                title="Enregistrer le statut du devis"
              >
                <option value="" disabled>Statut du devis…</option>
                <option value="negociation">🔄 Négociation (relancé aujourd'hui)</option>
                <option value="approuve">✅ Approuvé</option>
                <option value="rejete">❌ Rejeté</option>
              </select>
              <button
                className="btn btn-sm btn-cancel"
                onClick={() => handleRetirer(d)}
                title="Retirer de la todo-list de relance (statut inchangé)"
              >
                ✓ Retirer
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
