"""
One-off script: sync Beat.author_name from user DB profiles.
Run from project root (where .env lives):
  docker compose run --rm beat python /app/../scripts/sync_author_names.py
Or directly:
  python scripts/sync_author_names.py
"""
import asyncio
import os
from pathlib import Path

# Load .env
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

import asyncpg


def _dsn(user, password, host, port, db):
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


async def main():
    user = os.environ["DB_USER"]
    password = os.environ["PASSWORD"]
    port_inside = os.environ.get("DB_PORT_INSIDE", "5432")

    user_dsn = _dsn(user, password, os.environ["USER_DB_HOST"], port_inside, os.environ["USER_DB_NAME"])
    beat_dsn = _dsn(user, password, os.environ["BEAT_DB_HOST"], port_inside, os.environ["BEAT_DB_NAME"])

    user_conn = await asyncpg.connect(user_dsn)
    beat_conn = await asyncpg.connect(beat_dsn)

    try:
        profiles = await user_conn.fetch("SELECT user_id, username FROM profiles WHERE username IS NOT NULL")
        print(f"Found {len(profiles)} profiles")

        updated = 0
        for row in profiles:
            result = await beat_conn.execute(
                "UPDATE beats SET author_name = $1 WHERE author_id = $2 AND author_name IS DISTINCT FROM $1",
                row["username"], row["user_id"],
            )
            count = int(result.split()[-1])
            if count:
                print(f"  {row['username']}: {count} beat(s) updated")
                updated += count

        print(f"\nDone. Total beats updated: {updated}")
    finally:
        await user_conn.close()
        await beat_conn.close()


asyncio.run(main())
