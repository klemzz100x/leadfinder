import { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { addLeadsToList } from '../api.js'

export default function AddToListBtn({ lead, lists, onAdded }) {
  const [open, setOpen] = useState(false)
  const [adding, setAdding] = useState(null)
  const [done, setDone] = useState(null)
  const [duplicate, setDuplicate] = useState(null)
  const [pos, setPos] = useState(null)
  const btnRef = useRef(null)
  const dropdownRef = useRef(null)

  useEffect(() => {
    if (!open) return
    const handler = (e) => {
      if (!btnRef.current?.contains(e.target) && !dropdownRef.current?.contains(e.target)) {
        setOpen(false)
      }
    }
    const closeOnScroll = () => setOpen(false)
    document.addEventListener('mousedown', handler)
    window.addEventListener('scroll', closeOnScroll, true)
    return () => {
      document.removeEventListener('mousedown', handler)
      window.removeEventListener('scroll', closeOnScroll, true)
    }
  }, [open])

  if (!lists || lists.length === 0) return null

  const toggleOpen = () => {
    if (!open && btnRef.current) {
      const r = btnRef.current.getBoundingClientRect()
      setPos({ top: r.bottom + 4, right: window.innerWidth - r.right })
    }
    setOpen((v) => !v)
  }

  const handleAdd = async (list) => {
    setAdding(list.id)
    setDuplicate(null)
    try {
      const res = await addLeadsToList(list.id, [lead.id])
      if (res.added > 0) {
        setDone(list.id)
        onAdded?.(list)
        setTimeout(() => { setDone(null); setOpen(false) }, 900)
      } else {
        // Doublon (même nom+adresse déjà dans cette liste) : pas d'ajout,
        // pas d'incrément du compteur — juste un retour visuel clair.
        setDuplicate(list.id)
        setTimeout(() => setDuplicate(null), 1800)
      }
    } catch (e) {
      console.error(e)
    } finally {
      setAdding(null)
    }
  }

  return (
    <div className="atl-wrap">
      <button
        ref={btnRef}
        className="btn-add-list"
        onClick={toggleOpen}
        title="Ajouter à une liste"
      >
        + Liste
      </button>
      {open && pos && createPortal(
        <div
          className="atl-dropdown"
          ref={dropdownRef}
          style={{ position: 'fixed', top: pos.top, right: pos.right }}
        >
          <div className="atl-header">Ajouter à une liste</div>
          {lists.map(list => (
            <button
              key={list.id}
              className={`atl-item${done === list.id ? ' atl-done' : ''}${duplicate === list.id ? ' atl-duplicate' : ''}`}
              onClick={() => handleAdd(list)}
              disabled={!!adding}
              title={duplicate === list.id ? 'Déjà présent dans cette liste' : undefined}
            >
              {done === list.id && '✓ '}
              {duplicate === list.id ? '⚠ Déjà présent' : list.name}
              <span className="atl-count">{list.lead_count}</span>
            </button>
          ))}
        </div>,
        document.body
      )}
    </div>
  )
}
