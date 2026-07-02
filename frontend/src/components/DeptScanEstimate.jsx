import { useEffect, useState } from 'react'
import { fetchDepartementEstimate } from '../api.js'

// Estimation légère (API Geo gouv.fr, pas d'appel Overpass) du volume d'un
// scan département avant de le lancer — pour piloter soi-même l'ordre et le
// rythme de couverture plutôt que de tout scanner d'un coup.
export default function DeptScanEstimate({ codes }) {
  const [estimates, setEstimates] = useState([])
  const key = (codes || []).join(',')

  useEffect(() => {
    if (!codes || codes.length === 0) {
      setEstimates([])
      return
    }
    let cancelled = false
    Promise.all(codes.map(fetchDepartementEstimate))
      .then((results) => { if (!cancelled) setEstimates(results.filter(Boolean)) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  if (estimates.length === 0) return null

  const totalCommunes = estimates.reduce((s, e) => s + (e.communes || 0), 0)

  return (
    <p className="dept-scan-estimate">
      ≈ {totalCommunes} commune{totalCommunes > 1 ? 's' : ''} à scanner
      {estimates.length > 1 && (
        <span className="dept-scan-estimate-detail">
          {' '}({estimates.map((e) => `${e.name} : ${e.communes}`).join(', ')})
        </span>
      )}
    </p>
  )
}
