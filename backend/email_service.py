"""Envoi de l'email devis+site au client — SMTP Gmail (mot de passe
d'application, pas OAuth) plutôt qu'un service transactionnel (Resend) :
décision révisée en cours de session, l'utilisateur n'ayant pas de domaine
vérifiable dans l'immédiat. `smtplib`/`email.message` (stdlib Python),
aucune dépendance ajoutée.

Mode aperçu obligatoire avant tout envoi réel (garde-fou explicitement
demandé) : `send_or_preview(..., preview=True)` compose l'email et le
retourne sans jamais ouvrir de connexion SMTP.
"""

from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from .config import settings

log = logging.getLogger("leadfinder.email_service")

_TEMPLATE_PATH = Path(__file__).parent / "templates" / "email_devis.html"

_EMETTEUR_NOM = "Clément Garnero Nguyen"
_EMETTEUR_EMAIL = "clem.garnero753@gmail.com"

_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 587


@dataclass(slots=True)
class EmailPreview:
    to: str
    subject: str
    html_body: str
    devis_filename: str
    sent: bool = False
    error: Optional[str] = None


def _build_html(nom_etablissement: str, site_url: str, devis_numero: str) -> str:
    html = _TEMPLATE_PATH.read_text(encoding="utf-8")
    replacements = {
        "{{NOM_ETABLISSEMENT}}": nom_etablissement,
        "{{SITE_URL}}": site_url,
        "{{DEVIS_NUMERO}}": devis_numero,
        "{{EMETTEUR_NOM}}": _EMETTEUR_NOM,
        "{{EMETTEUR_EMAIL}}": _EMETTEUR_EMAIL,
    }
    for key, value in replacements.items():
        html = html.replace(key, value)
    return html


def _send_smtp(to: str, subject: str, html_body: str, devis_path: Path) -> None:
    msg = MIMEMultipart()
    msg["From"] = f"{_EMETTEUR_NOM} <{settings.GMAIL_ADDRESS}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with devis_path.open("rb") as f:
        part = MIMEApplication(f.read(), _subtype="pdf")
    part.add_header("Content-Disposition", "attachment", filename=devis_path.name)
    msg.attach(part)

    with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT, timeout=20) as server:
        server.starttls()
        server.login(settings.GMAIL_ADDRESS, settings.GMAIL_APP_PASSWORD)
        server.send_message(msg)


def send_or_preview(
    to: str,
    nom_etablissement: str,
    site_url: str,
    devis_path: Path,
    devis_numero: str,
    preview: bool,
) -> EmailPreview:
    subject = f"Votre site vitrine et devis — {nom_etablissement}"
    html_body = _build_html(nom_etablissement, site_url, devis_numero)
    result = EmailPreview(to=to, subject=subject, html_body=html_body, devis_filename=devis_path.name)

    if preview:
        return result

    if not settings.has_gmail:
        result.error = "GMAIL_ADDRESS/GMAIL_APP_PASSWORD non configurés"
        log.warning(result.error)
        return result

    try:
        _send_smtp(to, subject, html_body, devis_path)
        result.sent = True
    except (smtplib.SMTPException, OSError) as exc:
        result.error = str(exc)
        log.warning("Envoi email KO pour %r : %s", to, exc)

    return result
