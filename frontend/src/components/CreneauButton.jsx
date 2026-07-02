import { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'

// Bouton + popup dédié pour mettre en avant le créneau d'appel indicatif
// dans le menu des listes (plus visible qu'un simple badge discret) —
// affiche le créneau et rappelle explicitement qu'il reste indicatif,
// n'empêche jamais d'appeler en dehors.
export default function CreneauButton({ creneau, businessType }) {
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState(null)
  const btnRef = useRef(null)
  const popupRef = useRef(null)

  useEffect(() => {
    if (!open) return
    const handler = (e) => {
      if (!btnRef.current?.contains(e.target) && !popupRef.current?.contains(e.target)) {
        setOpen(false)
      }
    }
    const closeOnScroll = () => setOpen(false)
    document.addEventListener('mousedown', handler)
    window.addEventListener('scroll', closeOnScroll, true)
    return () => {
      document.removeEventListener('mousedown', handler)
      window.removeEventListener('scroll', closeOnScroll, true)
    }
  }, [open])

  if (!creneau) return null

  const toggleOpen = () => {
    if (!open && btnRef.current) {
      const r = btnRef.current.getBoundingClientRect()
      setPos({ top: r.bottom + 4, left: r.left })
    }
    setOpen((v) => !v)
  }

  return (
    <div className="creneau-btn-wrap">
      <button
        ref={btnRef}
        type="button"
        className="creneau-btn"
        onClick={toggleOpen}
        title="Créneau d'appel indicatif"
      >
        🕐 {creneau}
      </button>
      {open && pos && createPortal(
        <div
          className="creneau-popup"
          ref={popupRef}
          style={{ position: 'fixed', top: pos.top, left: pos.left }}
        >
          <div className="creneau-popup-title">📞 Meilleur moment pour appeler</div>
          <div className="creneau-popup-time">{creneau}</div>
          {businessType && <div className="creneau-popup-type">Secteur : {businessType}</div>}
          <p className="creneau-popup-note">
            Créneau indicatif, à ajuster selon le retour terrain — n'empêche pas d'appeler en dehors si besoin.
          </p>
        </div>,
        document.body
      )}
    </div>
  )
}
