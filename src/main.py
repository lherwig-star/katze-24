"""Kommandozeile - der einzige Einstiegspunkt.

Aufruf immer aus dem Projektordner:
    python -m src.main <befehl>

Beispiele:
    python -m src.main list
    python -m src.main crawl --shop demo_books --limit 10
    python -m src.main crawl
    python -m src.main deals
    python -m src.main send --dry-run
    python -m src.main stats
"""

from __future__ import annotations

import argparse
import logging
import sys

from src.crawlers import get_crawlers
from src.crawlers.base import REGISTRY
from src.dealengine import MIN_DISCOUNT_PCT, find_deals
from src.notifier import format_deal, get_notifier
from src.storage import Store

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def cmd_list(args: argparse.Namespace) -> None:
    get_crawlers()  # loest die Auto-Discovery aus
    if not REGISTRY:
        print("Keine Crawler gefunden.")
        return
    print(f"{'SHOP':<15} {'STATUS':<12} KLASSE")
    for shop, cls in sorted(REGISTRY.items()):
        status = "aktiv" if cls.enabled else "deaktiviert"
        print(f"{shop:<15} {status:<12} {cls.__name__}")


def cmd_crawl(args: argparse.Namespace) -> None:
    with Store() as store:
        total = 0
        for cls in get_crawlers(args.shop):
            crawler = cls()
            try:
                offers = crawler.run(limit=args.limit)
            except NotImplementedError as exc:
                print(f"  {cls.shop}: {exc}")
                continue
            except Exception:
                logging.exception("%s ist abgestuerzt", cls.shop)
                continue
            saved = store.save_offers(offers)
            total += saved
            print(f"  {cls.shop:<15} {saved} Angebote gespeichert")
        print(f"\nGesamt: {total}")


def cmd_deals(args: argparse.Namespace) -> None:
    with Store() as store:
        offers = store.current_offers(args.shop)
        deals = find_deals(store, offers, min_discount=args.min_discount)
        if not deals:
            stats = store.stats()
            print("Keine Deals gefunden.")
            if stats["tage_historie"] < 7:
                print(
                    f"Erst {stats['tage_historie']} Tag(e) Preishistorie - "
                    "das ist normal. Taeglich crawlen lassen."
                )
            return
        for deal in deals[: args.top]:
            print("\n" + format_deal(deal))


def cmd_send(args: argparse.Namespace) -> None:
    notifier = get_notifier("console" if args.dry_run else args.via)
    with Store() as store:
        offers = store.current_offers(args.shop)
        deals = find_deals(store, offers, min_discount=args.min_discount)

        sent = 0
        for deal in deals[: args.top]:
            if store.was_sent_recently(deal.offer.uid):
                continue
            if notifier.send(format_deal(deal)):
                sent += 1
                if not args.dry_run:
                    store.mark_sent(deal.offer.uid, deal.offer.price_cents)
        print(f"\n{sent} Deal(s) {'simuliert' if args.dry_run else 'verschickt'}")


def cmd_stats(args: argparse.Namespace) -> None:
    with Store() as store:
        for key, value in store.stats().items():
            print(f"{key:<15} {value}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="petdeals")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="verfuegbare Crawler anzeigen").set_defaults(
        func=cmd_list
    )

    p = sub.add_parser("crawl", help="Shops crawlen und speichern")
    p.add_argument("--shop", help="nur diesen Shop")
    p.add_argument("--limit", type=int, help="max. Angebote pro Shop (zum Testen)")
    p.set_defaults(func=cmd_crawl)

    p = sub.add_parser("deals", help="aktuelle Deals anzeigen")
    p.add_argument("--shop")
    p.add_argument("--min-discount", type=float, default=MIN_DISCOUNT_PCT)
    p.add_argument("--top", type=int, default=10)
    p.set_defaults(func=cmd_deals)

    p = sub.add_parser("send", help="Deals verschicken")
    p.add_argument("--shop")
    p.add_argument("--min-discount", type=float, default=MIN_DISCOUNT_PCT)
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--via", default="console",
                   help="console | file | telegram")
    p.add_argument("--dry-run", action="store_true",
                   help="nur anzeigen, nichts verschicken oder markieren")
    p.set_defaults(func=cmd_send)

    sub.add_parser("stats", help="Datenbank-Statistik").set_defaults(func=cmd_stats)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    setup_logging(args.verbose)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
