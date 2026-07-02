import { useState } from 'react'
import { USERS, getCurrentUser, setCurrentUser } from '../identity.js'

// Sélecteur "qui êtes-vous" — identité légère partagée entre Daniel et
// Clément sur la même base, pas une authentification (pas de mot de passe,
// aucun accès bloqué). Sert à tracer qui a lancé quel scan et à qui un lead
// est attribué dans une liste.
export default function IdentityPicker() {
  const [user, setUser] = useState(getCurrentUser())

  const handleChange = (e) => {
    const value = e.target.value
    setCurrentUser(value)
    setUser(value)
  }

  return (
    <select
      className="identity-picker"
      value={user}
      onChange={handleChange}
      title="Qui êtes-vous ? (sert juste à tracer qui a scanné/traité quoi)"
    >
      <option value="">👤 Qui êtes-vous ?</option>
      {USERS.map((name) => (
        <option key={name} value={name}>👤 {name}</option>
      ))}
    </select>
  )
}
