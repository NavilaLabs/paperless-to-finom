"""Configuration loaded from environment variables (or a .env file)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _get(name: str, default: str | None = None, required: bool = False) -> str:
    val = os.environ.get(name, default)
    if required and not val:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return val or ""


def _split_tags(raw: str) -> list[str]:
    return [t.strip() for t in raw.split(",") if t.strip()]


@dataclass(slots=True)
class Config:
    # --- Paperless ---
    paperless_url: str
    paperless_token: str

    # --- Tag-based selection / state machine ---
    # Documents carrying pending_tag get sent, then re-tagged to sent_tag.
    pending_tag: str = "finom-pending"
    sent_tag: str = "finom-sent"
    error_tag: str = "finom-error"

    # Optional extra server-side filters (all ANDed). Empty = ignore.
    correspondent_id: str = ""
    document_type_id: str = ""
    created_after: str = ""   # YYYY-MM-DD
    created_before: str = ""  # YYYY-MM-DD

    # Prefer the original uploaded file over the archived PDF/A version.
    prefer_original: bool = True

    # --- Finom ---
    finom_inbox_email: str = ""   # the import address Finom gave you

    # --- SMTP (to send the mail to Finom) ---
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_starttls: bool = True

    # --- Local audit DB ---
    db_path: Path = field(default_factory=lambda: Path("finom_sync.sqlite3"))

    # --- HTTP trigger (optional) ---
    trigger_token: str = ""

    # Safety: process at most this many docs per run (0 = unlimited)
    max_per_run: int = 0

    dry_run: bool = False

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            paperless_url=_get("PAPERLESS_URL", required=True).rstrip("/"),
            paperless_token=_get("PAPERLESS_TOKEN", required=True),
            pending_tag=_get("FINOM_PENDING_TAG", "finom-pending"),
            sent_tag=_get("FINOM_SENT_TAG", "finom-sent"),
            error_tag=_get("FINOM_ERROR_TAG", "finom-error"),
            correspondent_id=_get("FINOM_CORRESPONDENT_ID", ""),
            document_type_id=_get("FINOM_DOCUMENT_TYPE_ID", ""),
            created_after=_get("FINOM_CREATED_AFTER", ""),
            created_before=_get("FINOM_CREATED_BEFORE", ""),
            prefer_original=_get("FINOM_PREFER_ORIGINAL", "true").lower() != "false",
            finom_inbox_email=_get("FINOM_INBOX_EMAIL", ""),
            smtp_host=_get("SMTP_HOST", ""),
            smtp_port=int(_get("SMTP_PORT", "587")),
            smtp_user=_get("SMTP_USER", ""),
            smtp_password=_get("SMTP_PASSWORD", ""),
            smtp_from=_get("SMTP_FROM", "") or _get("SMTP_USER", ""),
            smtp_starttls=_get("SMTP_STARTTLS", "true").lower() != "false",
            db_path=Path(_get("FINOM_DB_PATH", "finom_sync.sqlite3")),
            trigger_token=_get("FINOM_TRIGGER_TOKEN", ""),
            max_per_run=int(_get("FINOM_MAX_PER_RUN", "0")),
            dry_run=_get("FINOM_DRY_RUN", "false").lower() == "true",
        )
