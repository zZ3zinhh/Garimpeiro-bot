# Used by the GitHub backup: decides if the PC has stopped working.
# If the bot ran recently (on the PC), the backup stays quiet.
# It writes "run=true" or "run=false" for the next step of the workflow.
import os
import sys

import db

STALE_AFTER_MINUTES = 25  # the PC runs every 10 min, so 25 min of silence means it's off


def main():
    force = "--force" in sys.argv
    minutes = db.minutes_since_last_run()
    if force:
        should_run, why = True, "forced by hand"
    elif minutes is None:
        should_run, why = True, "the bot never ran"
    elif minutes > STALE_AFTER_MINUTES:
        should_run, why = True, f"last run was {minutes:.0f} min ago"
    else:
        should_run, why = False, f"last run was only {minutes:.0f} min ago"

    print(f"should run: {should_run} ({why})")
    output_file = os.environ.get("GITHUB_OUTPUT")  # GitHub gives us this file
    if output_file:
        with open(output_file, "a", encoding="utf-8") as f:
            f.write(f"run={'true' if should_run else 'false'}\n")


if __name__ == "__main__":
    main()
