# The bot: fetch deals -> filter for each person -> alert -> remember what was sent.
# People, tags and history all live in the Supabase database.
#
# How to run (from the project folder):
#   py bot\main.py          -> real run (sends notifications)
#   py bot\main.py --test   -> only prints, sends nothing and saves nothing
import os
import sys
import time

import db
from sources import pelando, promobit
from matcher import CATEGORIES, evaluate
from notify import alert

sys.stdout.reconfigure(encoding="utf-8")  # so accents print correctly on Windows
RUNNER = os.environ.get("BOT_RUNNER", "pc")  # who is running: "pc" or "github"


def fetch_all_deals(people):
    """Fetch the 'recent' pages + the pages of every category someone follows."""
    pages = [(pelando.fetch, None), (promobit.fetch, None)]
    for person in people:
        for followed in person.get("categories", []):
            names = CATEGORIES.get(followed["category"], {})
            pages += [(pelando.fetch, c) for c in names.get("pelando", [])]
            pages += [(promobit.fetch, c) for c in names.get("promobit", [])]

    by_id = {}  # id -> deal (so the same deal never shows up twice)
    for fetch, category in dict.fromkeys(pages):  # dict.fromkeys removes repeats
        try:
            for deal in fetch(category):
                if deal["id"] in by_id:  # already seen: just merge the categories
                    by_id[deal["id"]]["categories"] += deal["categories"]
                else:
                    by_id[deal["id"]] = deal
        except Exception as error:
            print(f"! Error reading {fetch.__module__} {category or ''}: {error}")
        time.sleep(1)  # a polite pause between pages
    return list(by_id.values())


_enriched = set()  # deals whose Promobit offer page was already opened in this run


def enrich(deal):
    """Opens the Promobit offer page of a deal (once) to learn its price meter and
    whether the store is verified. Only called for deals someone might get alerted about."""
    if deal["site"] != "promobit" or deal["id"] in _enriched:
        return
    _enriched.add(deal["id"])
    try:
        deal.update(promobit.fetch_details(deal["link"]))
    except Exception as error:
        print(f"   ! Could not read the offer page: {error}")
    time.sleep(0.5)  # a polite pause


def main():
    test_mode = "--test" in sys.argv
    people = db.load_people()
    deals = fetch_all_deals(people)
    print(f"{len(deals)} deals found on the sites.")

    already_sent = db.load_sent_keys()
    count = 0

    for person in people:
        for deal in deals:
            key = f"{person['id']}|{deal['id']}"
            if key in already_sent:
                continue
            result = evaluate(deal, person, enrich)
            if result is None:
                continue
            reason, detail = result
            print(f"-> {person['name']}: [{reason}] {deal['title'][:60]} | {deal['price']}")
            if test_mode:
                continue
            try:
                alert(person, deal, reason, detail)
                db.save_sent(person["id"], deal, reason)
                already_sent.add(key)
                count += 1
            except Exception as error:
                print("   ! Could not send alert:", error)

    if not test_mode:
        db.mark_run(RUNNER)
    print(f"Done! {count} alerts sent.")


if __name__ == "__main__":
    main()
