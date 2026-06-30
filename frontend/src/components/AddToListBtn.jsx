import { useState, useEffect, useRef } from 'react'
import { addLeadsToList } from '../api.js'

export default function AddToListBtn({ lead, lists, onAdded }) {
  const [open, setOpen] = useState(false)
  const [adding, setAdding] = useState(null)
  const [done, setDone] = useState(null)
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  if (!lists || lists.length === 0) return null

  const handleAdd = async (list) => {
    setAdding(list.id)
    try {
      await addLeadsToList(list.id, [lead.id])
      setDone(list.id)
      onAdded?.(list)
      setTimeout(() => { setDone(null); setOpen(false) }, 900)
    } catch (e) {
      console.error(e)
    } finally {
      setAdding(null)
    }
  }

  return (
    <div className="atl-wrap" ref={ref}>
      <button
        className="btn-add-list"
        onClick={() => setOpen(v => !v)}
        title="Ajouter à une liste"
      >
        + Liste
      </button>
      {open && (
        <div className="atl-dropdown">
          <div className="atl-header">Ajouter à une liste</div>
          {lists.map(list => (
            <button
              key={list.id}
              className={`atl-item${done === list.id ? ' atl-done' : ''}`}
              onClick={() => handleAdd(list)}
              disabled={!!adding}
            >
              {done === list.id ? '✓ ' : ''}{list.name}
              <span className="atl-count">{list.lead_count}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
