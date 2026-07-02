import { useState, useEffect, useCallback } from 'react'
import {
  createList, deleteList,
  fetchListLeads, fetchListStats,
  removeLeadFromList, patchListLead,
} from '../api.js'
import ListLeadRow, { STATUSES } from './ListLeadRow.jsx'
import ListStats from './ListStats.jsx'

export default function ListsView({ lists, onListsChange }) {
  const [selected, setSelected]     = useState(null)
  const [listLeads, setListLeads]   = useState([])
  const [stats, setStats]           = useState(null)
  const [loading, setLoading]       = useState(false)
  const [newName, setNewName]       = useState('')
  const [statusFilter, setFilter]   = useState('')

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

  const handleStatusChange = async (lead, status) => {
    await patchListLead(selected.id, lead.id, { status })
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
              onClick={() => loadList(list)}
            >
              <span className="list-nav-name">{list.name}</span>
              <span className="list-nav-count">{list.lead_count}</span>
              <button className="list-nav-del" onClick={e => handleDelete(list, e)} title="Supprimer">×</button>
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
                />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
