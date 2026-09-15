import psycopg
import redis

from apply_pipeline.config import Settings, get_settings

VECTOR_VERSION_QUERY = """
    SELECT extversion
    FROM pg_extension
    WHERE extname = 'vector';
"""


def check_postgres(settings: Settings) -> str:
    database_url = str(settings.database_url).replace(
        "postgresql+psycopg://",
        "postgresql://",
        1,
    )

    with (
        psycopg.connect(database_url, connect_timeout=5) as conn,
        conn.cursor() as cursor,
    ):
        cursor.execute("SELECT version();")
        postgres_row = cursor.fetchone()

        if postgres_row is None:
            raise RuntimeError("Could not get PostgreSQL version")

        postgres_version = postgres_row[0]

        cursor.execute(VECTOR_VERSION_QUERY)
        vector_row = cursor.fetchone()

        if vector_row is None:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cursor.execute(VECTOR_VERSION_QUERY)
            vector_row = cursor.fetchone()

        if vector_row is None:
            raise RuntimeError("Could not get pgvector version")

        vector_version = vector_row[0]

    return f"{postgres_version}, pgvector {vector_version}"


def check_redis(settings: Settings) -> str:
    client = redis.Redis.from_url(
        str(settings.redis_url),
        socket_connect_timeout=5,
    )

    try:
        client.ping()
        info = client.info()
        redis_version = info["redis_version"]

        return f"Redis {redis_version}"
    finally:
        client.close()


def main() -> int:
    settings = get_settings()
    failed = False

    try:
        postgres_version = check_postgres(settings)
        print(f"PostgreSQL: OK - {postgres_version}")
    except (psycopg.Error, RuntimeError) as error:
        print(f"PostgreSQL: FAIL - {error}")
        failed = True

    try:
        redis_version = check_redis(settings)
        print(f"Redis: OK - {redis_version}")
    except (redis.exceptions.RedisError, RuntimeError) as error:
        print(f"Redis: FAIL - {error}")
        failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
