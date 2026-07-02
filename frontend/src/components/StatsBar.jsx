import EstimatedRevenue from './EstimatedRevenue.jsx'

const LABELS = {
  chaud: { label: 'Chauds', emoji: '🔥' },
  tiede: { label: 'Tièdes', emoji: '🟠' },
  froid: { label: 'Froids', emoji: '⚪' },
  a_verifier: { label: 'À vérifier', emoji: '❓' },
}

export default function StatsBar({ summary }) {
  const { city, total, by_temperature, by_status } = summary
  return (
    <div className="stats-bar">
      <span className="stats-city">{city}</span>
      <span className="stats-total">{total} business</span>
      {Object.entries(by_temperature).map(([temp, count]) => (
        <span key={temp} className={`badge temp-${temp}`}>
          {LABELS[temp]?.emoji || '?'} {count} {LABELS[temp]?.label || temp}
        </span>
      ))}
      <EstimatedRevenue count={by_temperature?.chaud || 0} compact />
    </div>
  )
}
