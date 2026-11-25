import time
from pathlib import Path

from .storage import database


def main():
    sql_dir = Path(__file__).resolve().parents[1] / "postgres"
    for attempt in range(20):
        try:
            with database() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(3410273)")
                cursor.execute((sql_dir / "init.sql").read_text())
                cursor.execute((sql_dir / "upgrade.sql").read_text())
        except Exception:
            if attempt == 19:
                raise
            time.sleep(3)
        else:
            return


if __name__ == "__main__":
    main()
