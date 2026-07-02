import { useRef, useState } from 'react'
import { scanArea } from '../api.js'

// Pause de politesse entre deux scans département consécutifs — en plus du
// rate-limit Nominatim déjà respecté à l'intérieur d'un scan, ça évite
// d'enchaîner trop d'appels Overpass sans interruption sur un gros lot.
const DELAY_BETWEEN_MS = 1500

// 'empty' (0 résultat) est distinct de 'ok' (résultats trouvés) : un scan qui
// répond sans erreur mais ne ramène rien mérite un signal différent d'un
// vrai succès — sur un département entier, 0 est presque toujours le signe
// qu'Overpass a échoué en silence (rate-limit épuisé, etc.), pas qu'il n'y a
// vraiment aucun commerce.
const STATUS_ICON = { pending: '⏳', running: '🔄', ok: '✅', empty: '⚠️', error: '❌' }

export default function BatchScanPanel({ codes, departements, onComplete }) {
  const [results, setResults] = useState(() =>
    codes.map((code) => ({
      code,
      name: departements.find((d) => d.code === code)?.name || code,
      status: 'pending',
      total: null,
      message: null,
    }))
  )
  const [running, setRunning] = useState(false)
  const [started, setStarted] = useState(false)
  const stopRef = useRef(false)

  const updateRow = (code, patch) => {
    setResults((prev) => prev.map((r) => (r.code === code ? { ...r, ...patch } : r)))
  }

  const start = async () => {
    stopRef.current = false
    setStarted(true)
    setRunning(true)

    for (let i = 0; i < codes.length; i++) {
      if (stopRef.current) break
      const code = codes[i]
      const name = departements.find((d) => d.code === code)?.name || code
      updateRow(code, { status: 'running' })
      console.info(`[scan par lot] Démarrage ${name} (${code}) — ${i + 1}/${codes.length}`)
      try {
        const summaries = await scanArea({ departements: [code] })
        const total = summaries.reduce((s, x) => s + (x.total || 0), 0)
        if (total === 0) {
          console.warn(`[scan par lot] ${name} (${code}) : 0 business trouvé — probablement un échec Overpass silencieux, pas une vraie absence de commerces`)
        } else {
          console.info(`[scan par lot] ${name} (${code}) terminé : ${total} business trouvés`)
        }
        updateRow(code, { status: total === 0 ? 'empty' : 'ok', total })
      } catch (e) {
        console.error(`[scan par lot] ${name} (${code}) échec :`, e)
        updateRow(code, { status: 'error', message: e.message })
        // Un échec sur un département ne bloque pas les suivants.
      }
      if (i < codes.length - 1 && !stopRef.current) {
        await new Promise((r) => setTimeout(r, DELAY_BETWEEN_MS))
      }
    }

    setRunning(false)
    onComplete?.()
  }

  const stop = () => {
    stopRef.current = true
  }

  const doneCount = results.filter((r) => ['ok', 'empty', 'error'].includes(r.status)).length
  const errorCount = results.filter((r) => r.status === 'error').length
  const emptyCount = results.filter((r) => r.status === 'empty').length
  const totalLeads = results.reduce((s, r) => s + (r.total || 0), 0)

  return (
    <div className="batch-scan-panel">
      {!started ? (
        <button className="btn btn-scan" onClick={start}>
          🔍 Lancer le scan par lot ({codes.length} département{codes.length > 1 ? 's' : ''})
        </button>
      ) : (
        <>
          <div className="batch-scan-header">
            <span>
              {running
                ? `Scan en cours… ${doneCount}/${codes.length}`
                : `Terminé : ${doneCount}/${codes.length} (${errorCount} échec${errorCount > 1 ? 's' : ''}, ${emptyCount} à 0 résultat, ${totalLeads} business trouvés au total)`}
            </span>
            {running && (
              <button className="btn btn-sm btn-cancel" onClick={stop}>
                ⏹ Stop
              </button>
            )}
          </div>
          <ul className="batch-scan-list">
            {results.map((r) => (
              <li key={r.code} className={`batch-scan-row batch-scan-${r.status}`}>
                <span className="batch-scan-icon">{STATUS_ICON[r.status]}</span>
                <span className="batch-scan-name">{r.name}</span>
                {r.status === 'ok' && <span className="batch-scan-count">{r.total} business</span>}
                {r.status === 'empty' && (
                  <span className="batch-scan-error" title="0 résultat — probablement un échec Overpass silencieux, à relancer">
                    0 résultat — à relancer
                  </span>
                )}
                {r.status === 'error' && (
                  <span className="batch-scan-error" title={r.message}>Échec — voir console</span>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
