export function googleMapsUrl(lead) {
  const query = [lead.name, lead.address || lead.city].filter(Boolean).join(', ')
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}`
}
