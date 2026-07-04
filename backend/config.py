"""Configuration centralisée — lue depuis .env, jamais de clés en dur."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Base de données PostgreSQL (Neon, ou toute URL postgresql://...)
    DATABASE_URL: str = ""

    # Clés API optionnelles — le projet tourne sans aucune d'elles.
    PSI_API_KEY: str = ""            # PageSpeed Insights (Phase 2)
    GOOGLE_PLACES_API_KEY: str = ""  # Google Places API New (optionnel, bridé)
    BRAVE_API_KEY: str = ""          # Brave Search (optionnel)

    # Phase 8 : génération + envoi automatisé (site + devis + email).
    ANTHROPIC_API_KEY: str = ""      # Claude API — rédaction du contenu des sites
    CLOUDFLARE_API_TOKEN: str = ""   # Déploiement Cloudflare Pages headless
    CLOUDFLARE_ACCOUNT_ID: str = ""
    GMAIL_ADDRESS: str = ""          # Envoi email (SMTP + mot de passe d'application)
    GMAIL_APP_PASSWORD: str = ""

    @property
    def has_psi(self) -> bool:
        return bool(self.PSI_API_KEY)

    @property
    def has_google(self) -> bool:
        return bool(self.GOOGLE_PLACES_API_KEY)

    @property
    def has_brave(self) -> bool:
        return bool(self.BRAVE_API_KEY)

    @property
    def has_anthropic(self) -> bool:
        return bool(self.ANTHROPIC_API_KEY)

    @property
    def has_cloudflare(self) -> bool:
        return bool(self.CLOUDFLARE_API_TOKEN and self.CLOUDFLARE_ACCOUNT_ID)

    @property
    def has_gmail(self) -> bool:
        return bool(self.GMAIL_ADDRESS and self.GMAIL_APP_PASSWORD)


settings = Settings()
