import { useState } from 'react'
import { saveCreneaux } from '../api.js'

const emptyDef = () => ({ types: [], creneau: '' })

export default function CreneauxEditor({ familles, types, onClose, onSave }) {
  // Deep-clone pour ne pas muter l'état du parent pendant l'édition
  const [fams, setFams] = useState(() => JSON.parse(JSON.stringify(familles)))
  const [newFamName, setNewFamName] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const assignedTypes = new Set(Object.values(fams).flatMap((f) => f.types || []))
  const availableTypes = (types || []).filter((t) => !assignedTypes.has(t))

  const updateField = (fam, field, value) => {
    setFams((prev) => ({ ...prev, [fam]: { ...prev[fam], [field]: value } }))
  }

  const removeTypeFromFam = (fam, type) => {
    setFams((prev) => ({
      ...prev,
      [fam]: { ...prev[fam], types: prev[fam].types.filter((t) => t !== type) },
    }))
  }

  const addTypeToFam = (fam, type) => {
    if (!type) return
    setFams((prev) => ({
      ...prev,
      [fam]: { ...prev[fam], types: [...(prev[fam].types || []), type] },
    }))
  }

  const addFamille = () => {
    const name = newFamName.trim()
    if (!name || fams[name] !== undefined) return
    setFams((prev) => ({ ...prev, [name]: emptyDef() }))
    setNewFamName('')
  }

  const removeFamille = (fam) => {
    setFams((prev) => {
      const next = { ...prev }
      delete next[fam]
      return next
    })
  }

  const handleSave = async () => {
    setSaving(true)
    setError('')
    try {
      await saveCreneaux(fams)
      onSave(fams)
      onClose()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) onClose()
  }

  return (
    <div className="modal-overlay" onClick={handleOverlayClick}>
      <div className="modal-panel" role="dialog" aria-modal="true" aria-label="Éditer les créneaux d'appel">
        <div className="modal-header">
          <h2>📞 Créneaux d'appel par famille de secteur</h2>
          <button className="modal-close" onClick={onClose} title="Fermer">✕</button>
        </div>

        <div className="modal-body">
          <p className="creneaux-editor-hint">
            Créneau indicatif pour prioriser les appels — n'empêche jamais d'appeler en dehors si besoin.
          </p>

          {Object.entries(fams).map(([fam, def]) => (
            <div key={fam} className="cat-editor-group">
              <div className="cat-editor-header">
                <span className="cat-editor-name">{fam}</span>
                <button className="btn btn-sm btn-danger" onClick={() => removeFamille(fam)}>
                  Supprimer
                </button>
              </div>

              <div className="cat-editor-types">
                {(def.types || []).map((type) => (
                  <span key={type} className="cat-type-pill">
                    {type}
                    <button onClick={() => removeTypeFromFam(fam, type)} title={`Retirer "${type}" de cette famille`}>
                      ✕
                    </button>
                  </span>
                ))}

                {availableTypes.length > 0 && (
                  <select
                    className="cat-type-select"
                    defaultValue=""
                    onChange={(e) => {
                      if (e.target.value) {
                        addTypeToFam(fam, e.target.value)
                        e.target.value = ''
                      }
                    }}
                  >
                    <option value="">+ Ajouter un type…</option>
                    {availableTypes.map((t) => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                )}

                {(def.types || []).length === 0 && availableTypes.length === 0 && (
                  <span style={{ color: 'var(--muted)', fontSize: '0.8rem' }}>
                    Aucun type disponible
                  </span>
                )}
              </div>

              <div className="cat-editor-budget">
                <label>
                  Créneau indicatif
                  <input
                    type="text"
                    placeholder="ex : 15h–18h"
                    value={def.creneau ?? ''}
                    onChange={(e) => updateField(fam, 'creneau', e.target.value)}
                  />
                </label>
              </div>
            </div>
          ))}

          <div className="cat-editor-new">
            <input
              type="text"
              className="cat-new-input"
              placeholder="Nom de la nouvelle famille…"
              value={newFamName}
              onChange={(e) => setNewFamName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && addFamille()}
            />
            <button
              className="btn btn-sm"
              onClick={addFamille}
              disabled={!newFamName.trim() || fams[newFamName.trim()] !== undefined}
            >
              + Créer
            </button>
          </div>

          {error && <p className="error">{error}</p>}
        </div>

        <div className="modal-footer">
          <button className="btn btn-export" onClick={onClose}>
            Annuler
          </button>
          <button className="btn btn-scan" onClick={handleSave} disabled={saving}>
            {saving ? 'Sauvegarde…' : '💾 Sauvegarder'}
          </button>
        </div>
      </div>
    </div>
  )
}
