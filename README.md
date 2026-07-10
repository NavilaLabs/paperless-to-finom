# paperless-to-finom

Sendet Rechnungen aus **Paperless-ngx** automatisch an die Import-Adresse deiner
Geschäftsbank **Finom**. Läuft als Cron-Job oder optional als kleine HTTP-API.

## Ablauf

1. Findet alle Dokumente mit dem Tag `finom-pending` (plus optionale Filter).
2. Lädt jedes Dokument herunter und benennt es nach dem von Paperless
   formatierten Dateinamen (oder deinem eigenen Template).
3. Verschickt es als E-Mail-Anhang an die Finom-Import-Adresse.
4. Setzt den Tag von `finom-pending` auf `finom-sent` (verhindert Doppelversand).
5. Protokolliert alles in einer lokalen SQLite-DB (`finom_sync.sqlite3`).

Schlägt der Versand fehl, bekommt das Dokument den Tag `finom-error` und
bleibt liegen.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # ausfüllen
```

Token in Paperless erzeugen: **My Profile → API-Token**.

## Nutzung

```bash
# Testlauf ohne zu senden:
python -m paperless_finom.cli sync --dry-run --json

# Echt senden:
python -m paperless_finom.cli sync

# Audit-Log ansehen:
python -m paperless_finom.cli history --limit 20

# Optionaler HTTP-Trigger:
python -m paperless_finom.cli serve --host 0.0.0.0 --port 8080
# -> POST /trigger  mit  Authorization: Bearer <FINOM_TRIGGER_TOKEN>
```

## Filter

Primär über den Tag `finom-pending`. Zusätzlich per `.env` einschränkbar:
Correspondent-ID, Document-Type-ID, Zeitraum (`created_after` / `created_before`).
Die IDs findest du in der Paperless-URL beim Filtern oder unter
`/api/correspondents/` bzw. `/api/document_types/`.

## Dateiname

Ohne `FINOM_FILENAME_TEMPLATE` wird der Name genutzt, den Paperless beim
Download im `Content-Disposition`-Header liefert (respektiert dein
`PAPERLESS_FILENAME_FORMAT`). Eigenes Schema z. B.:

```
FINOM_FILENAME_TEMPLATE={created}_{correspondent}_{title}
# -> 2026-01-15_Hetzner_Rechnung-Hetzner-Jan.pdf
```

## Deployment

Siehe `deploy/systemd.md` für Cron, systemd-Timer und Docker/Coolify.

## Öffentliche API?

Für „Rechnung → Finom" reicht der Cron-`sync` und braucht **keinen** offenen
Port. Der `serve`-Modus ist nur nötig, wenn du einen Webhook/Button willst –
dann unbedingt hinter Reverse-Proxy/Cloudflare und mit gesetztem
`FINOM_TRIGGER_TOKEN` betreiben.
```
