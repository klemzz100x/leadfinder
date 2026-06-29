import { useState } from 'react'
import { saveCategories } from '../api.js'

export default function CategoryEditor({ categories, types, onClose, onSave }) {
  // Deep-clone to avoid mutating parent state during editing
  const [cats, setCats] = useState(() => JSON.parse(JSON.stringify(categories)))
  const [newCatName, setNewCatName] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  // Types already assigned across all categories
  const assignedTypes = new Set(Object.values(cats).flat())
  // Types available to add = data types not yet assigned anywhere
  const availableTypes = (types || []).filter((t) => !assignedTypes.has(t))

  const removeTypeFromCat = (cat, type) => {
    setCats((prev) => ({
      ...prev,
      [cat]: prev[cat].filter((t) => t !== type),
    }))
  }

  const addTypeToCat = (cat, type) => {
    if (!type) return
    setCats((prev) => ({
      ...prev,
      [cat]: [...(prev[cat] || []), type],
    }))
  }

  const addCategory = () => {
    const name = newCatName.trim()
    if (!name || cats[name] !== undefined) return
    setCats((prev) => ({ ...prev, [name]: [] }))
    setNewCatName('')
  }

  const removeCategory = (cat) => {
    setCats((prev) => {
      const next = { ...prev }
      delete next[cat]
      return next
    })
  }

  const handleSave = async () => {
    setSaving(true)
    setError('')
    try {
      await saveCategories(cats)
      onSave(cats)
      onClose()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  // Close on overlay click
  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) onClose()
  }

  return (
    <div className="modal-overlay" onClick={handleOverlayClick}>
      <div className="modal-panel" role="dialog" aria-modal="true" aria-label="Éditer les catégories">
        <div className="modal-header">
          <h2>⚙ Catégories métier</h2>
          <button className="modal-close" onClick={onClose} title="Fermer">✕</button>
        </div>

        <div className="modal-body">
          {Object.entries(cats).map(([cat, catTypes]) => (
            <div key={cat} className="cat-editor-group">
              <div className="cat-editor-header">
                <span className="cat-editor-name">{cat}</span>
                <button
                  className="btn btn-sm btn-danger"
                  onClick={() => removeCategory(cat)}
                >
                  Supprimer
                </button>
              </div>

              <div className="cat-editor-types">
                {catTypes.map((type) => (
                  <span key={type} className="cat-type-pill">
                    {type}
                    <button
                      onClick={() => removeTypeFromCat(cat, type)}
                      title={`Retirer "${type}" de cette catégorie`}
                    >
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
                        addTypeToCat(cat, e.target.value)
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

                {catTypes.length === 0 && availableTypes.length === 0 && (
                  <span style={{ color: 'var(--muted)', fontSize: '0.8rem' }}>
                    Aucun type disponible
                  </span>
                )}
              </div>
            </div>
          ))}

          <div className="cat-editor-new">
            <input
              type="text"
              className="cat-new-input"
              placeholder="Nom de la nouvelle catégorie…"
              value={newCatName}
              onChange={(e) => setNewCatName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && addCategory()}
            />
            <button
              className="btn btn-sm"
              onClick={addCategory}
              disabled={!newCatName.trim() || cats[newCatName.trim()] !== undefined}
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
