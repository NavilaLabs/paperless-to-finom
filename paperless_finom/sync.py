"""Core sync: find pending invoices, mail them to Finom, re-tag, audit."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .config import Config
from .mailer import Mailer
from .naming import build_filename
from .paperless import PaperlessClient, PaperlessDocument, PaperlessError
from .store import Store

log = logging.getLogger("paperless_finom")


@dataclass(slots=True)
class SyncResult:
    processed: int = 0
    sent: int = 0
    skipped: int = 0
    errors: int = 0
    details: list[dict] | None = None

    def as_dict(self) -> dict:
        return {
            "processed": self.processed,
            "sent": self.sent,
            "skipped": self.skipped,
            "errors": self.errors,
            "details": self.details or [],
        }


class SyncService:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.client = PaperlessClient(cfg.paperless_url, cfg.paperless_token)
        self.store = Store(cfg.db_path)
        self._correspondent_cache: dict[int, str] = {}
        self.mailer = Mailer(
            host=cfg.smtp_host,
            port=cfg.smtp_port,
            user=cfg.smtp_user,
            password=cfg.smtp_password,
            from_addr=cfg.smtp_from,
            starttls=cfg.smtp_starttls,
        )

    # ------------------------------------------------------------------
    def _correspondent_name(self, cid: int | None) -> str | None:
        if cid is None:
            return None
        if cid in self._correspondent_cache:
            return self._correspondent_cache[cid]
        try:
            r = self.client._get(f"correspondents/{cid}/")
            name = r.json().get("name")
        except PaperlessError:
            name = None
        self._correspondent_cache[cid] = name or ""
        return name

    # ------------------------------------------------------------------
    def run(self) -> SyncResult:
        cfg = self.cfg
        result = SyncResult(details=[])

        if not cfg.finom_inbox_email:
            raise RuntimeError("FINOM_INBOX_EMAIL is not configured.")

        pending_id = self.client.resolve_tag_id(cfg.pending_tag)
        if pending_id is None:
            log.info(
                "Pending tag %r does not exist yet; nothing to do.", cfg.pending_tag
            )
            return result

        sent_id = self.client.resolve_tag_id(cfg.sent_tag, create=True)
        error_id = self.client.resolve_tag_id(cfg.error_tag, create=True)

        docs = self.client.list_documents(
            tag_id=pending_id,
            correspondent_id=cfg.correspondent_id,
            document_type_id=cfg.document_type_id,
            created_after=cfg.created_after,
            created_before=cfg.created_before,
        )

        if cfg.max_per_run > 0:
            docs = docs[: cfg.max_per_run]

        log.info("Found %d document(s) tagged %r.", len(docs), cfg.pending_tag)

        for doc in docs:
            result.processed += 1
            try:
                self._process_one(doc, sent_id, error_id, result)
            except Exception as exc:  # noqa: BLE001 - want to continue the batch
                result.errors += 1
                log.exception("Failed on document %d", doc.id)
                self.store.record(
                    paperless_id=doc.id,
                    title=doc.title,
                    filename="",
                    finom_email=cfg.finom_inbox_email,
                    status="error",
                    error=str(exc),
                )
                result.details.append(
                    {"id": doc.id, "status": "error", "error": str(exc)}
                )
                if not cfg.dry_run and error_id is not None:
                    try:
                        self.client.swap_tags(
                            doc.id, doc.tags, remove=None, add=error_id
                        )
                    except PaperlessError:
                        log.warning("Could not add error tag to %d", doc.id)

        return result

    # ------------------------------------------------------------------
    def _process_one(
        self,
        doc: PaperlessDocument,
        sent_id: int | None,
        error_id: int | None,
        result: SyncResult,
    ) -> None:
        cfg = self.cfg

        if self.store.already_sent(doc.id):
            result.skipped += 1
            result.details.append({"id": doc.id, "status": "skipped-db"})
            log.info("Doc %d already in DB as sent; skipping.", doc.id)
            # still fix the tag so it stops matching next run
            if not cfg.dry_run and sent_id is not None:
                self.client.swap_tags(
                    doc.id,
                    doc.tags,
                    remove=self.client.resolve_tag_id(cfg.pending_tag),
                    add=sent_id,
                )
            return

        content, server_name = self.client.download(doc.id, cfg.prefer_original)
        filename = build_filename(
            title=doc.title,
            created=doc.created,
            correspondent_name=self._correspondent_name(doc.correspondent),
            doc_id=doc.id,
            metadata_original_filename=doc.metadata_original_filename,
            media_filename=doc.media_filename,
            server_filename=server_name,
        )

        if cfg.dry_run:
            log.info(
                "[dry-run] would send doc %d as %r to %s",
                doc.id,
                filename,
                cfg.finom_inbox_email,
            )
            result.details.append(
                {"id": doc.id, "status": "dry-run", "filename": filename}
            )
            return

        self.mailer.send_document(
            to_addr=cfg.finom_inbox_email,
            filename=filename,
            content=content,
            subject=filename,
            body=f"Automated invoice import from Paperless.\nDocument: {doc.title}",
        )

        self.store.record(
            paperless_id=doc.id,
            title=doc.title,
            filename=filename,
            finom_email=cfg.finom_inbox_email,
            status="sent",
        )

        pending_id = self.client.resolve_tag_id(cfg.pending_tag)
        self.client.swap_tags(doc.id, doc.tags, remove=pending_id, add=sent_id)

        result.sent += 1
        result.details.append({"id": doc.id, "status": "sent", "filename": filename})
        log.info("Sent doc %d as %r to Finom.", doc.id, filename)

    def close(self) -> None:
        self.store.close()
