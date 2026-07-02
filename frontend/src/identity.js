// Identité légère (pas une vraie authentification) : sert uniquement à savoir
// "qui utilise l'app en ce moment" pour tracer les scans et l'attribution des
// leads sur la base partagée — aucun mot de passe, aucun accès restreint.
const STORAGE_KEY = 'leadfinder_user'

export const USERS = ['Daniel', 'Clément']

export function getCurrentUser() {
  return localStorage.getItem(STORAGE_KEY) || ''
}

export function setCurrentUser(name) {
  if (name) {
    localStorage.setItem(STORAGE_KEY, name)
  } else {
    localStorage.removeItem(STORAGE_KEY)
  }
}
