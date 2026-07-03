// Gamification : chaque lead chaud représente un site vendable entre 500 et
// 1000 € — affiché comme une fourchette de potentiel, jamais un chiffre
// unique (on ne sait pas combien vont réellement signer). Reste une
// estimation "plafond" (si 100% des leads chauds achetaient), pas une
// projection basée sur l'activité réelle — cf. `label` pour préciser ce que
// représente le nombre selon le contexte d'appel (liste, recherche, carte).
export default function EstimatedRevenue({ count, compact = false, label = 'potentiel estimé' }) {
  if (!count) return null
  const min = count * 500
  const max = count * 1000
  const fmt = (n) => n.toLocaleString('fr-FR')
  return (
    <span
      className={`estimated-revenue${compact ? ' estimated-revenue-compact' : ''}`}
      title={`Estimation indicative : ${count} lead${count > 1 ? 's' : ''} chaud${count > 1 ? 's' : ''} × 500–1000 € par site vendu`}
    >
      💰 {fmt(min)} € – {fmt(max)} €{!compact && <span className="estimated-revenue-label"> {label}</span>}
    </span>
  )
}
