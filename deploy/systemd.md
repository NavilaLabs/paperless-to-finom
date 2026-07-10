# Deployment-Varianten

## A) Klassischer Cron
```cron
# alle 30 Minuten
*/30 * * * * cd /opt/paperless-finom && /opt/paperless-finom/.venv/bin/python -m paperless_finom.cli sync >> /var/log/finom-sync.log 2>&1
```

## B) systemd Timer (empfohlen auf Linux-Host)

`/etc/systemd/system/finom-sync.service`
```ini
[Unit]
Description=Paperless -> Finom sync
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/opt/paperless-finom
EnvironmentFile=/opt/paperless-finom/.env
ExecStart=/opt/paperless-finom/.venv/bin/python -m paperless_finom.cli sync
```

`/etc/systemd/system/finom-sync.timer`
```ini
[Unit]
Description=Run Finom sync periodically

[Timer]
OnCalendar=*:0/30
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
systemctl enable --now finom-sync.timer
systemctl start finom-sync.service   # einmal manuell testen
journalctl -u finom-sync.service -f
```

## C) Docker / Coolify
```bash
docker build -t paperless-finom .

# Cron-Modus (einmal laufen, dann exit):
docker run --rm --env-file .env -v finom_data:/data paperless-finom sync

# HTTP-Trigger-Modus (Dauerbetrieb):
docker run -d --env-file .env -v finom_data:/data -p 8080:8080 \
  paperless-finom serve --host 0.0.0.0
```
In Coolify: als Scheduled Task den `sync`-Command mit `*/30 * * * *` einplanen,
oder als Service mit `serve` laufen lassen und per Cloudflare-geschützter Route
den `/trigger`-Endpoint aufrufen.
```
