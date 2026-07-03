import { useState, useEffect, useCallback } from 'react'
import {
  createList, deleteList, renameList, patchList,
  fetchListLeads, fetchListStats,
  removeLeadFromList, patchListLead,
} from '../api.js'
import ListLeadRow, { STATUSES } from './ListLeadRow.jsx'
import ListStats from './ListStats.jsx'
import { USERS, getCurrentUser } from '../identity.js'

export const PRIORITES = [
  { value: '',          label: 'Aucune priorité', icon: '⚪' },
  { value: 'urgent',    label: 'Urgent',          icon: '🔴' },
  { value: 'important', label: 'Important',       icon: '🟠' },
  { value: 'a_faire',   label: 'À faire',         icon: '🟡' },
]
const PRIORITE_MAP = Object.fromEntries(PRIORITES.map(p => [p.value, p]))

export default function ListsView({ lists, onListsChange, creneauxMap }) {
  const [selected, setSelected]     = useState(null)
  const [listLeads, setListLeads]   = useState([])
  const [stats, setStats]           = useState(null)
  const [loading, setLoading]       = useState(false)
  const [newName, setNewName]       = useState('')
  const [statusFilter, setFilter]   = useState('')
  const [renamingId, setRenamingId] = useState(null)
  const [renameValue, setRenameValue] = useState('')

  const loadList = useCallback(async (list) => {
    setSelected(list)
    setLoading(true)
    setListLeads([])
    setStats(null)
    const [leads, s] = await Promise.all([
      fetchListLeads(list.id),
      fetchListStats(list.id),
    ])
    setListLeads(leads)
    setStats(s)
    setLoading(false)
  }, [])

  const refreshAll = useCallback(async () => {
    if (!selected) return
    const [leads, s] = await Promise.all([
      fetchListLeads(selected.id),
      fetchListStats(selected.id),
    ])
    setListLeads(leads)
    setStats(s)
  }, [selected])

  // Polling multi-utilisateurs toutes les 5 secondes
  useEffect(() => {
    if (!selected) return
    const id = setInterval(refreshAll, 5000)
    return () => clearInterval(id)
  }, [selected, refreshAll])

  const handleCreate = async (e) => {
    e.preventDefault()
    if (!newName.trim()) return
    const list = await createList(newName.trim())
    onListsChange([list, ...lists])
    setNewName('')
  }

  const handleDelete = async (list, e) => {
    e.stopPropagation()
    if (!window.confirm(`Supprimer "${list.name}" et tous ses leads ?`)) return
    await deleteList(list.id)
    onListsChange(lists.filter(l => l.id !== list.id))
    if (selected?.id === list.id) { setSelected(null); setListLeads([]); setStats(null) }
  }

  const startRename = (list, e) => {
    e.stopPropagation()
    setRenamingId(list.id)
    setRenameValue(list.name)
  }

  const commitRename = async (list) => {
    const trimmed = renameValue.trim()
    setRenamingId(null)
    if (!trimmed || trimmed === list.name) return
    await renameList(list.id, trimmed)
    onListsChange(lists.map(l => l.id === list.id ? { ...l, name: trimmed } : l))
    if (selected?.id === list.id) setSelected(prev => ({ ...prev, name: trimmed }))
  }

  const handleListAssign = async (list, assignedTo) => {
    await patchList(list.id, { assigned_to: assignedTo })
    onListsChange(lists.map(l => l.id === list.id ? { ...l, assigned_to: assignedTo } : l))
    if (selected?.id === list.id) setSelected(prev => ({ ...prev, assigned_to: assignedTo }))
  }

  const handleListPriorite = async (list, priorite) => {
    await patchList(list.id, { priorite })
    onListsChange(lists.map(l => l.id === list.id ? { ...l, priorite } : l))
    if (selected?.id === list.id) setSelected(prev => ({ ...prev, priorite }))
  }

  const handleStatusChange = async (lead, status) => {
    // `by` : identité de l'auteur, sert à attribuer l'appel/devis à Clément
    // ou Daniel dans l'onglet Performance (cf. lead_events côté backend).
    await patchListLead(selected.id, lead.id, { status, by: getCurrentUser() })
    setListLeads(prev => prev.map(l => l.id === lead.id ? { ...l, list_status: status } : l))
    const s = await fetchListStats(selected.id)
    setStats(s)
  }

  const handleNotes = async (lead, notes) => {
    await patchListLead(selected.id, lead.id, { notes })
    setListLeads(prev => prev.map(l => l.id === lead.id ? { ...l, list_notes: notes } : l))
  }

  const handleBudget = async (lead, fields) => {
    await patchListLead(selected.id, lead.id, fields)
    setListLeads(prev => prev.map(l => l.id === lead.id ? { ...l, ...fields } : l))
  }

  const handleAssign = async (lead, assignedTo) => {
    await patchListLead(selected.id, lead.id, { assigned_to: assignedTo })
    setListLeads(prev => prev.map(l => l.id === lead.id ? { ...l, assigned_to: assignedTo } : l))
  }

  const handleDevisEnvoye = async (lead, checked) => {
    await patchListLead(selected.id, lead.id, { devis_envoye: checked })
    // Coché = horodaté côté serveur à "maintenant" ; on ne connaît pas la
    // valeur exacte tant que la réponse n'a pas de payload, mais l'heure
    // locale suffit pour l'affichage immédiat (re-fetch la corrigerait sinon).
    setListLeads(prev => prev.map(l => l.id === lead.id
      ? { ...l, devis_envoye_le: checked ? new Date().toISOString() : null }
      : l))
  }

  const handleRemove = async (lead) => {
    await removeLeadFromList(selected.id, lead.id)
    setListLeads(prev => prev.filter(l => l.id !== lead.id))
    const s = await fetchListStats(selected.id)
    setStats(s)
    // Update count in sidebar
    onListsChange(lists.map(l => l.id === selected.id ? { ...l, lead_count: (l.lead_count || 1) - 1 } : l))
  }

  const filtered = statusFilter ? listLeads.filter(l => l.list_status === statusFilter) : listLeads

  return (
    <div className="lists-view">
      {/* Sidebar */}
      <aside className="lists-sidebar">
        <form className="lists-create-form" onSubmit={handleCreate}>
          <input
            className="lists-create-input"
            type="text"
            value={newName}
            onChange={e => setNewName(e.target.value)}
            placeholder="Nouvelle liste…"
          />
          <button type="submit" className="btn btn-sm btn-create-list">+ Créer</button>
        </form>

        <div className="lists-nav">
          {lists.length === 0 && (
            <p className="lists-empty-hint">Créez votre première liste de prospection</p>
          )}
          {lists.map(list => (
            <div
              key={list.id}
              className={`list-nav-item${selected?.id === list.id ? ' active' : ''}`}
              onClick={() => renamingId !== list.id && loadList(list)}
            >
              <div className="list-nav-top">
                <span className="list-nav-priorite-dot" title={PRIORITE_MAP[list.priorite || '']?.label}>
                  {PRIORITE_MAP[list.priorite || '']?.icon}
                </span>
                {renamingId === list.id ? (
                  <input
                    className="list-nav-rename-input"
                    autoFocus
                    value={renameValue}
                    onChange={e => setRenameValue(e.target.value)}
                    onClick={e => e.stopPropagation()}
                    onBlur={() => commitRename(list)}
                    onKeyDown={e => {
                      if (e.key === 'Enter') { e.preventDefault(); commitRename(list) }
                      if (e.key === 'Escape') setRenamingId(null)
                    }}
                  />
                ) : (
                  <span className="list-nav-name">{list.name}</span>
                )}
                <span className="list-nav-count">{list.lead_count}</span>
                {renamingId !== list.id && (
                  <button className="list-nav-rename" onClick={e => startRename(list, e)} title="Renommer">✏️</button>
                )}
                <button className="list-nav-del" onClick={e => handleDelete(list, e)} title="Supprimer">×</button>
              </div>
              <div className="list-nav-meta" onClick={e => e.stopPropagation()}>
                <select
                  className="list-nav-meta-select"
                  value={list.assigned_to || ''}
                  onChange={e => handleListAssign(list, e.target.value)}
                  title="Attribuer cette liste"
                >
                  <option value="">Non attribuée</option>
                  {USERS.map(u => <option key={u} value={u}>{u}</option>)}
                </select>
                <select
                  className="list-nav-meta-select"
                  value={list.priorite || ''}
                  onChange={e => handleListPriorite(list, e.target.value)}
                  title="Priorité de cette liste"
                >
                  {PRIORITES.map(p => (
                    <option key={p.value} value={p.value}>{p.icon} {p.label}</option>
                  ))}
                </select>
              </div>
            </div>
          ))}
        </div>
      </aside>

      {/* Contenu principal */}
      <div className="lists-main">
        {!selected ? (
          <div className="lists-placeholder">
            <div className="lists-placeholder-icon">📋</div>
            <p>Sélectionnez une liste ou créez-en une nouvelle</p>
            <p className="lists-placeholder-sub">
              Ajoutez des leads depuis la vue Recherche via le bouton <strong>+ Liste</strong>
            </p>
          </div>
        ) : (
          <>
            <div className="list-detail-header">
              <h2 className="list-detail-title">{selected.name}</h2>
              <span className="list-detail-count">{listLeads.length} prospect{listLeads.length > 1 ? 's' : ''}</span>
            </div>

            {stats && <ListStats stats={stats} />}

            <div className="list-toolbar">
              <select
                className="list-status-filter"
                value={statusFilter}
                onChange={e => setFilter(e.target.value)}
              >
                <option value="">Tous les statuts ({listLeads.length})</option>
                {STATUSES.map(s => {
                  const count = stats?.by_status?.[s.value] || 0
                  if (!count) return null
                  return <option key={s.value} value={s.value}>{s.label} ({count})</option>
                })}
              </select>
            </div>

            <div className="list-leads-container">
              {loading && <p className="empty">Chargement…</p>}
              {!loading && filtered.length === 0 && (
                <p className="empty">
                  {listLeads.length === 0
                    ? 'Aucun lead dans cette liste. Ajoutez-en depuis la vue Recherche.'
                    : 'Aucun lead pour ce statut.'}
                </p>
              )}
              {filtered.map(lead => (
                <ListLeadRow
                  key={lead.id}
                  lead={lead}
                  onStatusChange={status => handleStatusChange(lead, status)}
                  onRemove={() => handleRemove(lead)}
                  onNotesChange={notes => handleNotes(lead, notes)}
                  onBudgetChange={fields => handleBudget(lead, fields)}
                  onAssignChange={assignedTo => handleAssign(lead, assignedTo)}
                  onDevisEnvoyeChange={checked => handleDevisEnvoye(lead, checked)}
                  creneau={creneauxMap?.[lead.business_type]}
                />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
