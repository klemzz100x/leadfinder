import { useEffect, useState, useCallback } from 'react'
import { fetchPerformance } from '../api.js'

const FIGHTERS = [
  { name: 'Clément', color: '#3b82f6' },
  { name: 'Daniel', color: '#ef4444' },
]

const PERIODS = [
  { value: 'day', label: 'Jour' },
  { value: 'week', label: 'Semaine' },
  { value: 'month', label: 'Mois' },
]

const EMPTY_USER = {
  appels_jour: 0, appels_periode: 0,
  devis_jour: 0, devis_periode: 0,
  ca_potentiel: 0, trend: [],
}

function fmtEuros(n) {
  return `${Math.round(n).toLocaleString('fr-FR')} €`
}

// Pas de websocket : un refresh à l'ouverture de l'onglet + un polling léger
// tant qu'il reste actif suffit pour un score "vivant" sans complexité d'infra.
const POLL_MS = 25000

export default function PerformanceView() {
  const [period, setPeriod] = useState('day')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback((p) => {
    fetchPerformance(p)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    setLoading(true)
    load(period)
    const id = setInterval(() => load(period), POLL_MS)
    return () => clearInterval(id)
  }, [period, load])

  if (loading && !data) return <p className="empty">Chargement de l'affrontement…</p>
  if (error) return <p className="error">{error}</p>
  if (!data) return null

  const users = FIGHTERS.map((f) => ({ ...f, stats: data.users[f.name] || EMPTY_USER }))
  const [left, right] = users
  const totalCa = left.stats.ca_potentiel + right.stats.ca_potentiel
  const leftPct = totalCa > 0 ? Math.round((left.stats.ca_potentiel / totalCa) * 100) : 50
  const leader =
    left.stats.ca_potentiel === right.stats.ca_potentiel
      ? null
      : (left.stats.ca_potentiel > right.stats.ca_potentiel ? left.name : right.name)

  return (
    <div className="perf-view">
      <div className="perf-period-selector">
        {PERIODS.map((p) => (
          <button
            key={p.value}
            className={`perf-period-btn${period === p.value ? ' active' : ''}`}
            onClick={() => setPeriod(p.value)}
          >
            {p.label}
          </button>
        ))}
      </div>

      <div className="perf-gauge-track">
        <div className="perf-gauge-fill" style={{ width: `${leftPct}%` }} />
      </div>

      <div className="perf-arena">
        {[left, right].map((u, i) => (
          <div
            key={u.name}
            className={`perf-fighter${leader === u.name ? ' perf-fighter-leading' : ''}`}
            style={{ '--fighter-color': u.color }}
          >
            {leader === u.name && <span className="perf-crown">👑</span>}
            <span className="perf-fighter-name">{u.name}</span>

            <span className="perf-score-label">CA potentiel ({PERIODS.find(p => p.value === period).label.toLowerCase()})</span>
            <span className="perf-score-value">{fmtEuros(u.stats.ca_potentiel)}</span>

            <div className="perf-stat-row">
              <div className="perf-stat">
                <span className="perf-stat-value">{u.stats.appels_jour}</span>
                <span className="perf-stat-label">📞 Appels aujourd'hui</span>
              </div>
              <div className="perf-stat">
                <span className="perf-stat-value">{u.stats.appels_periode}</span>
                <span className="perf-stat-label">📞 Appels période</span>
              </div>
              <div className="perf-stat">
                <span className="perf-stat-value">{u.stats.devis_periode}</span>
                <span className="perf-stat-label">📄 Devis envoyés</span>
              </div>
            </div>

            {u.stats.trend.some((d) => d.count > 0) && (
              <div className="perf-trend">
                {u.stats.trend.map((d) => {
                  const max = Math.max(1, ...u.stats.trend.map((t) => t.count))
                  return (
                    <div key={d.date} className="perf-trend-col" title={`${d.date} : ${d.count}`}>
                      <div className="perf-trend-fill" style={{ height: `${(d.count / max) * 100}%` }} />
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        ))}

        <div className="perf-vs">VS</div>
      </div>
    </div>
  )
}
