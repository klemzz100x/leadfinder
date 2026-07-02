import { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { addLeadsToList, createList } from '../api.js'

// `lead` (un seul lead) ou `leadIds` (ajout groupé depuis une sélection
// multiple) — un seul des deux est nécessaire, `leadIds` prime si fourni.
export default function AddToListBtn({ lead, leadIds, lists, onAdded, onListCreated, label }) {
  const ids = leadIds || (lead ? [lead.id] : [])
  const isBulk = ids.length > 1
  const [open, setOpen] = useState(false)
  const [adding, setAdding] = useState(null)
  const [done, setDone] = useState(null)
  const [doneCount, setDoneCount] = useState(0)
  const [duplicate, setDuplicate] = useState(null)
  const [pos, setPos] = useState(null)
  const [creating, setCreating] = useState(false)
  const [newListName, setNewListName] = useState('')
  const [savingNew, setSavingNew] = useState(false)
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

  const toggleOpen = () => {
    if (!open && btnRef.current) {
      const r = btnRef.current.getBoundingClientRect()
      setPos({ top: r.bottom + 4, right: window.innerWidth - r.right })
    }
    setCreating(false)
    setOpen((v) => !v)
  }

  const handleAdd = async (list) => {
    if (ids.length === 0) return
    setAdding(list.id)
    setDuplicate(null)
    try {
      const res = await addLeadsToList(list.id, ids)
      if (res.added > 0) {
        setDone(list.id)
        setDoneCount(res.added)
        onAdded?.(list, res.added)
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

  const handleCreateAndAdd = async (e) => {
    e.preventDefault()
    const name = newListName.trim()
    if (!name || ids.length === 0) return
    setSavingNew(true)
    try {
      const list = await createList(name)
      const res = await addLeadsToList(list.id, ids)
      onListCreated?.({ ...list, lead_count: res.added || 0 })
      setNewListName('')
      setCreating(false)
      setDone(list.id)
      setDoneCount(res.added || 0)
      setTimeout(() => { setDone(null); setOpen(false) }, 900)
    } catch (e) {
      console.error(e)
    } finally {
      setSavingNew(false)
    }
  }

  return (
    <div className="atl-wrap">
      <button
        ref={btnRef}
        className="btn-add-list"
        onClick={toggleOpen}
        disabled={ids.length === 0}
        title={isBulk ? `Ajouter ces ${ids.length} leads à une liste` : 'Ajouter à une liste'}
      >
        {label || (isBulk ? `+ Liste (${ids.length})` : '+ Liste')}
      </button>
      {open && pos && createPortal(
        <div
          className="atl-dropdown"
          ref={dropdownRef}
          style={{ position: 'fixed', top: pos.top, right: pos.right }}
        >
          <div className="atl-header">
            {isBulk ? `Ajouter ${ids.length} leads à une liste` : 'Ajouter à une liste'}
          </div>
          {(!lists || lists.length === 0) && !creating && (
            <p className="atl-empty-hint">Aucune liste pour l'instant.</p>
          )}
          {lists?.map(list => (
            <button
              key={list.id}
              className={`atl-item${done === list.id ? ' atl-done' : ''}${duplicate === list.id ? ' atl-duplicate' : ''}`}
              onClick={() => handleAdd(list)}
              disabled={!!adding}
              title={duplicate === list.id ? 'Déjà présent dans cette liste' : undefined}
            >
              {done === list.id && `✓ ${isBulk ? `${doneCount} ajoutés` : ''} `}
              {duplicate === list.id ? '⚠ Déjà présent' : list.name}
              <span className="atl-count">{list.lead_count}</span>
            </button>
          ))}

          {creating ? (
            <form className="atl-new-form" onSubmit={handleCreateAndAdd}>
              <input
                type="text"
                className="atl-new-input"
                autoFocus
                placeholder="Nom de la nouvelle liste…"
                value={newListName}
                onChange={e => setNewListName(e.target.value)}
                disabled={savingNew}
              />
              <button type="submit" className="btn btn-sm" disabled={savingNew || !newListName.trim()}>
                {savingNew ? '…' : 'Créer'}
              </button>
            </form>
          ) : (
            <button type="button" className="atl-item atl-new-toggle" onClick={() => setCreating(true)}>
              + Nouvelle liste
            </button>
          )}
        </div>,
        document.body
      )}
    </div>
  )
}
