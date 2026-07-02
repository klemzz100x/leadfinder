import { useState, useEffect } from 'react'
import LeadRow from './LeadRow.jsx'
import AddToListBtn from './AddToListBtn.jsx'

export default function LeadList({ leads, onUpdate, lists, onListsChange }) {
  const [selected, setSelected] = useState(() => new Set())

  // Clé stable basée sur l'ensemble des ids affichés, pas sur la référence du
  // tableau `leads` : App.jsx recrée ce tableau (via .map()) à chaque mise à
  // jour d'un seul lead (ex: "marquer appelé"), ce qui viderait la sélection
  // à chaque clic si on se basait sur la référence. On ne réinitialise que
  // lorsque les leads affichés changent réellement (nouvelle recherche/filtre).
  const leadsKey = leads.map((l) => l.id).join(',')
  useEffect(() => {
    setSelected(new Set())
  }, [leadsKey])

  if (!leads.length) return null

  const allSelected = leads.length > 0 && selected.size === leads.length

  const toggleSelectAll = () => {
    setSelected(allSelected ? new Set() : new Set(leads.map((l) => l.id)))
  }

  const toggleSelect = (id) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const selectedIds = Array.from(selected)

  return (
    <div className="lead-list">
      <div className="lead-list-toolbar">
        <label className="lead-select-all">
          <input
            type="checkbox"
            checked={allSelected}
            onChange={toggleSelectAll}
          />
          Tout sélectionner ({leads.length})
        </label>
        {selected.size > 0 && (
          <div className="lead-bulk-actions">
            <span className="lead-bulk-count">{selected.size} sélectionné{selected.size > 1 ? 's' : ''}</span>
            <AddToListBtn
              leadIds={selectedIds}
              lists={lists}
              onAdded={(list, added) => {
                onListsChange?.(prev =>
                  prev.map(l => l.id === list.id ? { ...l, lead_count: (l.lead_count || 0) + (added || 0) } : l)
                )
                setSelected(new Set())
              }}
              onListCreated={(list) => {
                onListsChange?.(prev => [list, ...prev])
                setSelected(new Set())
              }}
            />
          </div>
        )}
      </div>

      {leads.map((lead) => (
        <LeadRow
          key={lead.id}
          lead={lead}
          onUpdate={onUpdate}
          lists={lists}
          onListsChange={onListsChange}
          selected={selected.has(lead.id)}
          onToggleSelect={toggleSelect}
        />
      ))}
    </div>
  )
}
