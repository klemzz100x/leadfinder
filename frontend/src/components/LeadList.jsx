import LeadRow from './LeadRow.jsx'

export default function LeadList({ leads, onUpdate }) {
  if (!leads.length) return null
  return (
    <div className="lead-list">
      {leads.map((lead) => (
        <LeadRow key={lead.id} lead={lead} onUpdate={onUpdate} />
      ))}
    </div>
  )
}
