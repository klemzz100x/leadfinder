import EstimatedRevenue from './EstimatedRevenue.jsx'

const STATUS_META = {
  a_contacter:   { label: 'À contacter',   color: '#60a5fa' },
  repondeur:     { label: 'Répondeur',      color: '#eab308' },
  rappel:        { label: 'Rappel',         color: '#a78bfa' },
  injoignable:   { label: 'Injoignable',    color: '#6b7280' },
  pas_interesse: { label: 'Pas intéressé',  color: '#ef4444' },
  devis_envoye:  { label: 'Devis envoyé',   color: '#f97316' },
  devis_relance: { label: 'Devis relancé',  color: '#fb923c' },
  devis_rejete:  { label: 'Devis rejeté',   color: '#7f1d1d' },
  closing:       { label: 'Closing',        color: '#22c55e' },
  facture_payee: { label: 'Facture payée',  color: '#10b981' },
}

// Prix forfaitaire d'un devis, pour un CA estimé nettement plus précis que
// le potentiel "si 100% des leads chauds achetaient" (EstimatedRevenue) :
// basé sur l'activité réelle de la liste (devis effectivement envoyés), pas
// sur sa taille brute.
const PRIX_DEVIS = 600

// Un lead ayant atteint devis_envoye/devis_relance/closing/facture_payee a,
// par définition, déjà reçu un devis à un moment du pipeline — même
// ensemble que `_DEVIS_PLUS` côté backend (taux_devis).
const STATUTS_DEVIS_ENVOYE = ['devis_envoye', 'devis_relance', 'closing', 'facture_payee']

function fmtEuros(n) {
  return `${n.toLocaleString('fr-FR')} €`
}

export default function ListStats({ stats }) {
  const { total, by_status, taux_contact, taux_devis, taux_closing, taux_closing_devis, closings_par_jour } = stats
  const recent = closings_par_jour.slice(-14)
  const maxCount = Math.max(1, ...recent.map(d => d.count))
  const devisEnvoyesCount = STATUTS_DEVIS_ENVOYE.reduce((sum, s) => sum + (by_status[s] || 0), 0)
  const caEstimePrecis = devisEnvoyesCount * PRIX_DEVIS

  return (
    <div className="list-stats">
      <div className="list-stats-kpis">
        <div className="kpi">
          <span className="kpi-value">{total}</span>
          <span className="kpi-label">Total</span>
        </div>
        <div className="kpi">
          <span className="kpi-value" style={{ color: '#60a5fa' }}>{taux_contact}%</span>
          <span className="kpi-label">Contacts réels</span>
        </div>
        <div className="kpi">
          <span className="kpi-value" style={{ color: '#f97316' }}>{taux_devis}%</span>
          <span className="kpi-label">Devis / contacté</span>
        </div>
        <div className="kpi kpi-highlight">
          <span className="kpi-value" style={{ color: '#22c55e' }}>{taux_closing}%</span>
          <span className="kpi-label">Taux closing</span>
        </div>
        <div className="kpi" title="Devis gagnés / (gagnés + rejetés) — hors devis encore en négociation">
          <span className="kpi-value" style={{ color: '#22c55e' }}>{taux_closing_devis}%</span>
          <span className="kpi-label">Close rate (devis tranchés)</span>
        </div>
      </div>

      <div className="list-stats-revenue-row">
        <EstimatedRevenue count={total} label="potentiel total de la liste (si 100% achetaient)" />
        {devisEnvoyesCount > 0 && (
          <span
            className="estimated-revenue estimated-revenue-precise"
            title={`${devisEnvoyesCount} devis envoyé${devisEnvoyesCount > 1 ? 's' : ''} × ${PRIX_DEVIS} € (prix forfaitaire d'un devis)`}
          >
            💶 {fmtEuros(caEstimePrecis)}
            <span className="estimated-revenue-label"> CA estimé sur devis envoyés ({devisEnvoyesCount} × {PRIX_DEVIS} €)</span>
          </span>
        )}
      </div>

      <div className="list-stats-breakdown">
        {Object.entries(STATUS_META).map(([key, meta]) => {
          const count = by_status[key] || 0
          if (!count) return null
          return (
            <span
              key={key}
              className="status-count-pill"
              style={{ color: meta.color, background: meta.color + '18', borderColor: meta.color + '40' }}
            >
              {meta.label} · {count}
            </span>
          )
        })}
      </div>

      {recent.length > 0 && (
        <div className="list-stats-chart">
          <span className="chart-title">Closings par jour</span>
          <div className="chart-bars">
            {recent.map(d => (
              <div key={d.date} className="chart-bar-col" title={`${d.date} : ${d.count}`}>
                <div className="chart-bar-fill" style={{ height: `${(d.count / maxCount) * 100}%` }} />
                <span className="chart-date-label">{d.date.slice(5)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
