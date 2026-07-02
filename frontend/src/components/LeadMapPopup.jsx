import { googleMapsUrl } from '../utils.js'
import AddToListBtn from './AddToListBtn.jsx'
import { CONTACT_STATUS_COLOR, CONTACT_STATUS_LABEL } from '../statusColors.js'

const TEMP_ICON = { chaud: '🔥', tiede: '🟠', froid: '❄️', a_verifier: '❓' }
const TEMP_LABEL = { chaud: 'Chaud', tiede: 'Tiède', froid: 'Froid', a_verifier: 'À vérifier' }

function normalizeWebsiteUrl(website) {
  return website.startsWith('http') ? website : `https://${website}`
}

export default function LeadMapPopup({ lead, lists, onListsChange, creneau }) {
  const website = lead.website || lead.gmaps_website
  const closedPermanently = lead.gmaps_status === 'closed_permanently'

  return (
    <div className="map-popup">
      <div className="map-popup-header">
        <span className={`temp-pill temp-${lead.temperature}`}>
          {TEMP_ICON[lead.temperature] || '?'} {TEMP_LABEL[lead.temperature] || lead.temperature}
        </span>
        {lead.contact_status && (
          <span
            className="gmaps-badge"
            style={{ background: `${CONTACT_STATUS_COLOR[lead.contact_status]}30`, color: CONTACT_STATUS_COLOR[lead.contact_status] }}
          >
            {CONTACT_STATUS_LABEL[lead.contact_status] || lead.contact_status}
          </span>
        )}
        {closedPermanently && <span className="gmaps-badge gmaps-closed">⛔ Fermé définitivement</span>}
        {creneau && (
          <span className="creneau-badge" title="Créneau indicatif, à ajuster selon retour terrain — n'empêche pas d'appeler en dehors">
            📞 {creneau}
          </span>
        )}
      </div>

      <div className="map-popup-name">{lead.name}</div>
      {lead.address && <div className="map-popup-address">{lead.address}</div>}

      <div className="map-popup-row">
        {lead.phone
          ? <a className="map-popup-link" href={`tel:${lead.phone}`}>📞 {lead.phone}</a>
          : <span className="map-popup-muted">Pas de téléphone</span>}
      </div>

      <div className="map-popup-row">
        {website
          ? (
            <a className="map-popup-link" href={normalizeWebsiteUrl(website)} target="_blank" rel="noreferrer">
              🌐 {website}
            </a>
          )
          : <span className="gmaps-badge gmaps-nosite">Aucun site</span>}
      </div>

      <div className="map-popup-actions">
        <a
          className="btn btn-sm"
          href={lead.gmaps_url || googleMapsUrl(lead)}
          target="_blank"
          rel="noreferrer"
        >
          📍 Google Maps
        </a>
        <AddToListBtn
          lead={lead}
          lists={lists}
          onAdded={(list) => onListsChange?.(prev =>
            prev.map(l => l.id === list.id ? { ...l, lead_count: (l.lead_count || 0) + 1 } : l)
          )}
          onListCreated={(list) => onListsChange?.(prev => [list, ...prev])}
        />
      </div>
    </div>
  )
}
