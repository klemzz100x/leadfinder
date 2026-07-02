import { useEffect, useState } from 'react'
import { fetchDashboard } from '../api.js'

function fmtEuros(n) {
  return `${Math.round(n).toLocaleString('fr-FR')} €`
}

export default function Dashboard({ onEditCategories }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    fetchDashboard()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <p className="empty">Chargement du dashboard…</p>
  if (error) return <p className="error">{error}</p>
  if (!data) return null

  return (
    <div className="dashboard-view">
      <div className="dashboard-kpis">
        <div className="dashboard-kpi">
          <span className="dashboard-kpi-value">{data.closes_ce_mois}</span>
          <span className="dashboard-kpi-label">Closes ce mois</span>
        </div>
        <div className="dashboard-kpi">
          <span className="dashboard-kpi-value">{fmtEuros(data.ca_reel_mois)}</span>
          <span className="dashboard-kpi-label">CA généré ce mois</span>
        </div>
        <div className="dashboard-kpi dashboard-kpi-streak">
          <span className="dashboard-kpi-value">🔥 {data.streak_jours}</span>
          <span className="dashboard-kpi-label">Jours de streak closing</span>
        </div>
        <div className="dashboard-kpi">
          <span className="dashboard-kpi-value">{data.categorie_top || '—'}</span>
          <span className="dashboard-kpi-label">Catégorie la plus rentable</span>
        </div>
      </div>

      <div className="dashboard-toolbar">
        <h3>Objectifs par catégorie — {data.month}</h3>
        <button className="btn btn-cat-editor" onClick={onEditCategories}>⚙ Éditer les objectifs</button>
      </div>

      <div className="dashboard-categories">
        {data.categories.map((cat) => {
          const caPct = cat.objectif_ca
            ? Math.min(100, Math.round((cat.ca_reel / cat.objectif_ca) * 100))
            : null
          const closesPct = cat.objectif_closes_mensuel
            ? Math.min(100, Math.round((cat.closes / cat.objectif_closes_mensuel) * 100))
            : null

          return (
            <div key={cat.name} className="dashboard-cat-card">
              <div className="dashboard-cat-header">
                <span className="dashboard-cat-name">{cat.name}</span>
                <span className="dashboard-cat-summary">
                  {cat.objectif_closes_mensuel
                    ? `${cat.closes}/${cat.objectif_closes_mensuel} closes`
                    : `${cat.closes} close${cat.closes > 1 ? 's' : ''}`}
                  {' · '}
                  {cat.objectif_ca ? `${fmtEuros(cat.ca_reel)}/${fmtEuros(cat.objectif_ca)}` : fmtEuros(cat.ca_reel)}
                </span>
              </div>

              {closesPct !== null && (
                <div className="dashboard-progress-track" title="Progression closes">
                  <div className="dashboard-progress-fill dashboard-progress-closes" style={{ width: `${closesPct}%` }} />
                </div>
              )}
              <div className="dashboard-progress-track" title="Progression CA">
                <div
                  className="dashboard-progress-fill dashboard-progress-ca"
                  style={{ width: `${caPct ?? (cat.ca_reel > 0 ? 100 : 0)}%` }}
                />
              </div>

              {(cat.budget_min || cat.budget_max) && (
                <span className="dashboard-cat-budget">
                  Budget cible / deal : {cat.budget_min === cat.budget_max
                    ? fmtEuros(cat.budget_min)
                    : `${fmtEuros(cat.budget_min || 0)} – ${fmtEuros(cat.budget_max || 0)}`}
                </span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
