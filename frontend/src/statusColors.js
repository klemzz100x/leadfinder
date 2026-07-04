// Palette partagée entre les cards de liste (ListLeadRow.jsx) et la carte
// (FranceMap.jsx / LeadMapPopup.jsx) — source unique pour rester cohérent
// entre les deux vues, comme demandé.
//
// Statuts volontairement absents (pas de couleur négative/positive encore) :
// a_contacter, repondeur, rappel — traités comme "neutre", pas de changement.
export const CONTACT_STATUS_COLOR = {
  injoignable: '#f59e0b',     // orange — à retenter, pas mort
  pas_interesse: '#b91c1c',   // rouge sombre — définitif (distinct du rouge
                               // "chaud" #ef4444 utilisé par la température,
                               // pour ne pas les confondre sur la carte)
  devis_envoye: '#22c55e',    // vert — devis fait
  devis_relance: '#22c55e',
  // Rejeté APRÈS un devis envoyé — distinct de pas_interesse (jamais atteint
  // le stade devis) pour pouvoir calculer un vrai close rate sur les devis
  // tranchés (gagné vs rejeté), cf. taux_closing_devis côté backend.
  devis_rejete: '#7f1d1d',
  closing: '#3b82f6',         // bleu — closé
  facture_payee: '#3b82f6',
}

export const CONTACT_STATUS_LABEL = {
  injoignable: 'Injoignable (à retenter)',
  pas_interesse: 'Pas intéressé',
  devis_envoye: 'Devis fait',
  devis_relance: 'Devis fait',
  devis_rejete: 'Devis rejeté',
  closing: 'Closé',
  facture_payee: 'Closé',
}
