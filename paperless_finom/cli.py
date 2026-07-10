"""CLI: `python -m paperless_finom.cli sync` (for cron)."""
from __future__ import annotations

import argparse
import json
import logging
import sys

from .config import Config
from .sync import SyncService


def _load_dotenv() -> None:
    """Load a .env file if python-dotenv is available; silent otherwise."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass


def cmd_sync(args: argparse.Namespace) -> int:
    cfg = Config.from_env()
    if args.dry_run:
        cfg.dry_run = True
    svc = SyncService(cfg)
    try:
        result = svc.run()
    finally:
        svc.close()
    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
    else:
        print(
            f"processed={result.processed} sent={result.sent} "
            f"skipped={result.skipped} errors={result.errors}"
        )
    return 1 if result.errors else 0


def cmd_history(args: argparse.Namespace) -> int:
    cfg = Config.from_env()
    from .store import Store
    store = Store(cfg.db_path)
    for row in store.recent(args.limit):
        print(f"[{row['sent_at']}] #{row['paperless_id']} "
              f"{row['status']:8} {row['filename']} "
              f"{'-> ' + row['error'] if row['error'] else ''}")
    store.close()
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    # Imported lazily so cron users don't need FastAPI installed.
    from .server import run_server
    cfg = Config.from_env()
    run_server(cfg, host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="paperless-finom")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("sync", help="Send pending invoices to Finom (cron).")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_sync)

    h = sub.add_parser("history", help="Show recent audit log entries.")
    h.add_argument("--limit", type=int, default=20)
    h.set_defaults(func=cmd_history)

    sv = sub.add_parser("serve", help="Run the optional HTTP trigger API.")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8080)
    sv.set_defaults(func=cmd_serve)

    return p


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
