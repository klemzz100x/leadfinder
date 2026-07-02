import EstimatedRevenue from './EstimatedRevenue.jsx'

const STATUS_META = {
  a_contacter:   { label: 'À contacter',   color: '#60a5fa' },
  repondeur:     { label: 'Répondeur',      color: '#eab308' },
  rappel:        { label: 'Rappel',         color: '#a78bfa' },
  injoignable:   { label: 'Injoignable',    color: '#6b7280' },
  pas_interesse: { label: 'Pas intéressé',  color: '#ef4444' },
  devis_envoye:  { label: 'Devis envoyé',   color: '#f97316' },
  devis_relance: { label: 'Devis relancé',  color: '#fb923c' },
  closing:       { label: 'Closing',        color: '#22c55e' },
  facture_payee: { label: 'Facture payée',  color: '#10b981' },
}

export default function ListStats({ stats }) {
  const { total, by_status, taux_contact, taux_devis, taux_closing, closings_par_jour } = stats
  const recent = closings_par_jour.slice(-14)
  const maxCount = Math.max(1, ...recent.map(d => d.count))

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
      </div>

      <EstimatedRevenue count={total} />

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
