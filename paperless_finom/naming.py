"""Build a clean, Finom-friendly filename for a document.

Source priority (first non-empty wins), configurable via FINOM_FILENAME_SOURCE:

  "template"  -> render FINOM_FILENAME_TEMPLATE from document fields
  "original"  -> original_filename from the /metadata/ endpoint (the name the
                 file had when it was uploaded — usually the cleanest)
  "server"    -> the name Paperless puts in the download Content-Disposition
                 header (respects your PAPERLESS_FILENAME_FORMAT)
  "media"     -> media_filename from /metadata/ (internal storage name, e.g.
                 "0000377.pdf" — rarely what you want)

Default order if FINOM_FILENAME_SOURCE is unset:
  template (if a template is set) -> original -> server -> media -> title

Template placeholders: {title} {created} {correspondent} {doc_id} {ext}
"""

from __future__ import annotations

import os
import re
from pathlib import Path

_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_DASHES = re.compile(r"[-\s]+")


def sanitize(name: str, keep_ext: bool = True) -> str:
    # media_filename can be a full storage path
    # (e.g. "NavilaLabs/2026/Rechnung/.../FIN_Rechnung_....pdf"); we only
    # want the final component. Split on both separators to be safe.
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    p = Path(name)
    stem = p.stem if keep_ext else name
    ext = p.suffix if keep_ext else ""
    stem = _ILLEGAL.sub(" ", stem).strip()
    stem = _DASHES.sub("-", stem).strip("-")
    if not stem:
        stem = "document"
    return f"{stem}{ext}"


def _render_template(
    template: str,
    *,
    title: str,
    created: str | None,
    correspondent_name: str | None,
    doc_id: int,
    ext: str,
) -> str:
    created_short = (created or "")[:10]
    rendered = template.format(
        title=title or f"document-{doc_id}",
        created=created_short,
        correspondent=correspondent_name or "",
        doc_id=doc_id,
        ext=ext,
    )
    if not rendered.endswith(ext):
        rendered = f"{rendered}{ext}"
    return rendered


def build_filename(
    *,
    title: str,
    created: str | None,
    correspondent_name: str | None,
    doc_id: int,
    metadata_original_filename: str | None = None,
    media_filename: str | None = None,
    server_filename: str | None = None,
    fallback_ext: str = ".pdf",
) -> str:
    template = os.environ.get("FINOM_FILENAME_TEMPLATE", "").strip()
    source = os.environ.get("FINOM_FILENAME_SOURCE", "").strip().lower()

    # Figure out an extension from whatever source has one.
    ext = ""
    for cand in (metadata_original_filename, server_filename, media_filename):
        if cand and Path(cand).suffix:
            ext = Path(cand).suffix
            break
    if not ext:
        ext = fallback_ext

    def by_source(name: str) -> str | None:
        if name == "template":
            if not template:
                return None
            return _render_template(
                template,
                title=title,
                created=created,
                correspondent_name=correspondent_name,
                doc_id=doc_id,
                ext=ext,
            )
        if name == "original":
            return metadata_original_filename
        if name == "server":
            return server_filename
        if name == "media":
            return media_filename
        return None

    # Explicit source requested.
    if source:
        chosen = by_source(source)
        if chosen:
            return sanitize(chosen)

    # Default priority chain.
    for name in ("template", "original", "server", "media"):
        chosen = by_source(name)
        if chosen:
            return sanitize(chosen)

    return sanitize(f"{title or ('document-' + str(doc_id))}{ext}")
