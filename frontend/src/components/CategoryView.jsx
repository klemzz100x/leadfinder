import { useState } from 'react'
import LeadRow from './LeadRow.jsx'

function tempCounts(leads) {
  const c = { chaud: 0, tiede: 0, froid: 0, a_verifier: 0 }
  leads.forEach((l) => { if (l.temperature in c) c[l.temperature]++ })
  return c
}

export default function CategoryView({ leads, categories, onUpdate }) {
  const [collapsed, setCollapsed] = useState({})

  const toggle = (name) =>
    setCollapsed((prev) => ({ ...prev, [name]: !prev[name] }))

  // Build reverse map : business_type → category name
  const typeToCategory = {}
  Object.entries(categories).forEach(([cat, types]) => {
    types.forEach((t) => { typeToCategory[t] = cat })
  })

  // Initialize groups in category order, then "Autres"
  const groups = {}
  Object.keys(categories).forEach((cat) => { groups[cat] = [] })
  groups['Autres'] = []

  leads.forEach((lead) => {
    const cat = typeToCategory[lead.business_type]
    const target = cat && groups[cat] !== undefined ? cat : 'Autres'
    groups[target].push(lead)
  })

  return (
    <div className="category-view">
      {Object.entries(groups).map(([name, groupLeads]) => {
        if (groupLeads.length === 0) return null
        const counts = tempCounts(groupLeads)
        const isCollapsed = Boolean(collapsed[name])

        return (
          <div key={name} className="category-group">
            <div className="category-header" onClick={() => toggle(name)}>
              <div className="category-header-left">
                <span className="category-chevron">{isCollapsed ? '▶' : '▼'}</span>
                <span className="category-name">{name}</span>
                <span className="category-count">{groupLeads.length} leads</span>
              </div>
              <div className="category-temp-counts">
                {counts.chaud > 0 && (
                  <span className="cat-badge cat-chaud">🔥 {counts.chaud}</span>
                )}
                {counts.tiede > 0 && (
                  <span className="cat-badge cat-tiede">🟠 {counts.tiede}</span>
                )}
                {counts.froid > 0 && (
                  <span className="cat-badge cat-froid">❄️ {counts.froid}</span>
                )}
                {counts.a_verifier > 0 && (
                  <span className="cat-badge cat-verif">❓ {counts.a_verifier}</span>
                )}
              </div>
            </div>

            {!isCollapsed && (
              <div className="category-leads">
                {groupLeads.map((lead) => (
                  <LeadRow key={lead.id} lead={lead} onUpdate={onUpdate} />
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
