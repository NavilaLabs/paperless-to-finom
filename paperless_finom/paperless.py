"""Thin client for the Paperless-ngx REST API.

Only the pieces we need: resolve tag names -> ids, list documents by tag
(plus optional filters), read metadata, download the file with the
server-formatted filename, and swap tags after a successful send.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import requests


@dataclass(slots=True)
class PaperlessDocument:
    id: int
    title: str
    tags: list[int]
    correspondent: int | None
    document_type: int | None
    created: str | None
    original_file_name: str | None
    archived_file_name: str | None
    # From the /metadata/ endpoint:
    media_filename: str | None = None  # e.g. "0000377.pdf" (stored file)
    metadata_original_filename: str | None = None  # original upload name


class PaperlessError(RuntimeError):
    pass


_FILENAME_RE = re.compile(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', re.IGNORECASE)


def _filename_from_content_disposition(header: str | None) -> str | None:
    if not header:
        return None
    m = _FILENAME_RE.search(header)
    if not m:
        return None
    from urllib.parse import unquote

    return unquote(m.group(1)).strip()


class PaperlessClient:
    def __init__(self, base_url: str, token: str, timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Token {token}",
                "Accept": "application/json",
            }
        )

    # ---- internal helpers -------------------------------------------------
    def _url(self, path: str) -> str:
        return f"{self.base_url}/api/{path.lstrip('/')}"

    def _get(self, path: str, **kwargs) -> requests.Response:
        # allow_redirects=False so a missing trailing slash (which Django
        # answers with a 301 to the slashed URL) surfaces loudly instead of
        # silently following through to the HTML login page.
        kwargs.setdefault("allow_redirects", False)
        r = self.session.get(self._url(path), timeout=self.timeout, **kwargs)
        if r.is_redirect or r.status_code in (301, 302):
            loc = r.headers.get("Location", "")
            if "login" in loc or "accounts" in loc:
                raise PaperlessError(
                    f"GET {path} redirected to login ({loc!r}). "
                    "Your token is likely missing/invalid, or the URL is wrong."
                )
            raise PaperlessError(
                f"GET {path} unexpectedly redirected to {loc!r}. "
                "Check the trailing slash on the endpoint."
            )
        if r.status_code >= 400:
            raise PaperlessError(f"GET {path} -> {r.status_code}: {r.text[:300]}")
        # A 200 that is actually the HTML login page means auth silently failed.
        ctype = r.headers.get("Content-Type", "")
        if "text/html" in ctype:
            raise PaperlessError(
                f"GET {path} returned HTML instead of JSON — you are not "
                "authenticated. Check PAPERLESS_TOKEN and PAPERLESS_URL."
            )
        return r

    # ---- tags -------------------------------------------------------------
    def resolve_tag_id(self, name: str, create: bool = False) -> int | None:
        r = self._get("tags/", params={"name__iexact": name})
        results = r.json().get("results", [])
        if results:
            return results[0]["id"]
        if not create:
            return None
        cr = self.session.post(
            self._url("tags/"), json={"name": name}, timeout=self.timeout
        )
        if cr.status_code >= 400:
            raise PaperlessError(
                f"create tag {name!r} -> {cr.status_code}: {cr.text[:300]}"
            )
        return cr.json()["id"]

    # ---- documents --------------------------------------------------------
    def list_documents(
        self,
        tag_id: int,
        correspondent_id: str = "",
        document_type_id: str = "",
        created_after: str = "",
        created_before: str = "",
        with_metadata: bool = True,
    ) -> list[PaperlessDocument]:
        params: dict[str, str | int] = {
            "tags__id__all": tag_id,
            "ordering": "created",
            "page_size": 100,
        }
        if correspondent_id:
            params["correspondent__id"] = correspondent_id
        if document_type_id:
            params["document_type__id"] = document_type_id
        if created_after:
            params["created__date__gte"] = created_after
        if created_before:
            params["created__date__lte"] = created_before

        docs: list[PaperlessDocument] = []
        url = "documents/"
        first = True
        while url:
            r = self._get(url, params=params if first else None)
            first = False
            data = r.json()
            for d in data.get("results", []):
                doc = PaperlessDocument(
                    id=d["id"],
                    title=d.get("title") or f"document-{d['id']}",
                    tags=d.get("tags", []),
                    correspondent=d.get("correspondent"),
                    document_type=d.get("document_type"),
                    created=d.get("created"),
                    original_file_name=d.get("original_file_name"),
                    archived_file_name=d.get("archived_file_name"),
                )
                if with_metadata:
                    self._attach_metadata(doc)
                docs.append(doc)
            nxt = data.get("next")
            # 'next' is a full URL; strip base so _get can rebuild it
            url = nxt.replace(self._url(""), "") if nxt else None
        return docs

    def _attach_metadata(self, doc: PaperlessDocument) -> None:
        """Call documents/<id>/metadata/ and copy the filename fields onto
        the document. Note the mandatory trailing slash."""
        meta = self.get_metadata(doc.id)
        print(meta)
        doc.media_filename = meta.get("media_filename")
        doc.metadata_original_filename = meta.get("original_filename")

    def get_metadata(self, doc_id: int) -> dict:
        # Trailing slash is required — without it Paperless 301-redirects and
        # the request can fall through to the HTML login page.
        return self._get(f"documents/{doc_id}/metadata/").json()

    def download(self, doc_id: int, prefer_original: bool) -> tuple[bytes, str]:
        """Return (content_bytes, filename). Filename comes from the
        Content-Disposition header Paperless sends (its formatted name)."""
        params = {"original": "true"} if prefer_original else None
        r = self.session.get(
            self._url(f"documents/{doc_id}/download/"),
            params=params,
            timeout=self.timeout,
        )
        if r.status_code >= 400:
            raise PaperlessError(
                f"download {doc_id} -> {r.status_code}: {r.text[:200]}"
            )
        filename = _filename_from_content_disposition(
            r.headers.get("Content-Disposition")
        )
        return r.content, filename or f"document-{doc_id}.pdf"

    def swap_tags(
        self, doc_id: int, current_tags: list[int], remove: int | None, add: int | None
    ) -> None:
        new_tags = [t for t in current_tags if t != remove]
        if add is not None and add not in new_tags:
            new_tags.append(add)
        r = self.session.patch(
            self._url(f"documents/{doc_id}/"),
            json={"tags": new_tags},
            timeout=self.timeout,
        )
        if r.status_code >= 400:
            raise PaperlessError(
                f"patch tags {doc_id} -> {r.status_code}: {r.text[:200]}"
            )
