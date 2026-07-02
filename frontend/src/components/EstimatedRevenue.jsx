// Gamification : chaque lead chaud représente un site vendable entre 500 et
// 1000 € — affiché comme une fourchette de potentiel, jamais un chiffre
// unique (on ne sait pas combien vont réellement signer).
export default function EstimatedRevenue({ count, compact = false }) {
  if (!count) return null
  const min = count * 500
  const max = count * 1000
  const fmt = (n) => n.toLocaleString('fr-FR')
  return (
    <span
      className={`estimated-revenue${compact ? ' estimated-revenue-compact' : ''}`}
      title={`Estimation indicative : ${count} lead${count > 1 ? 's' : ''} chaud${count > 1 ? 's' : ''} × 500–1000 € par site vendu`}
    >
      💰 {fmt(min)} € – {fmt(max)} €{!compact && <span className="estimated-revenue-label"> potentiel estimé</span>}
    </span>
  )
}
