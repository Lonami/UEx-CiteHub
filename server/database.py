from aiosqlite import Connection
from collections import namedtuple
from dataclasses import asdict
import itertools
import sqlite3
import functools
import json
from .storage import Publication as StepPublication

DB_VERSION = 1
Version = namedtuple("Version", "version")
User = namedtuple("User", "username password salt token")
Source = namedtuple("Source", "owner key values_json task_json due")
Author = namedtuple(
    "Author", "owner source path full_name id first_name last_name extra_json"
)
Publication = namedtuple(
    "Publication", "owner source path by_self name id year ref extra_json"
)
PublicationAuthors = namedtuple(
    "PublicationAuthors", "owner source pub_path author_path"
)
Cites = namedtuple("Cites", "owner source pub_path cited_by")


def _transaction(func):
    @functools.wraps(func)
    async def wrapped(self, *args, **kwargs):
        if "cursor" in kwargs:
            # Already in a transaction
            return await func(self, *args, **kwargs)

        async with self._db.execute("BEGIN") as cursor:
            try:
                ret = await func(self, *args, cursor=cursor, **kwargs)
            except sqlite3.Error:
                await cursor.execute("ROLLBACK")
                raise
            else:
                await cursor.execute("COMMIT")
            return ret

    return wrapped


def _adapt_step_publications(step):
    for pub in step.self_publications:
        yield pub, 1

    for citations in step.citations.values():
        for cit in citations:
            yield cit, 0


class Select:
    def __init__(self, db: Connection, table: type, query: str, args: tuple):
        if query.count("?") != len(args):
            raise ValueError("query parameters count mismatch with arguments")

        self._db = db
        self._table = table
        self._query = query
        self._args = args
        self._cursor = None

    async def one(self):
        tup = await self._cursor.fetchone()
        if tup:
            return self._table(*tup)

    def __aiter__(self):
        return self

    async def __anext__(self):
        return self._table(*await self._cursor.__anext__())

    async def __aenter__(self):
        self._cursor = await self._db.execute(
            f"SELECT * FROM {self._table.__name__} {self._query}", self._args
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._cursor.close()


class Database:
    # Setup

    def __init__(self, path):
        self._db = Connection(lambda: sqlite3.connect(path, isolation_level=None))

    async def __aenter__(self):
        await self._db
        await self._db.execute("PRAGMA foreign_keys = ON;")

        try:
            tup = await self._select_one(Version)
        except sqlite3.OperationalError:
            await self._create_tables()
        else:
            if tup.version != DB_VERSION:
                await self._upgrade_tables()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._db.close()

    @_transaction
    async def _create_tables(self, cursor=None):
        await cursor.execute(
            """CREATE TABLE Version (
            version INTEGER,
            PRIMARY KEY(version)
        ) WITHOUT ROWID"""
        )
        await cursor.execute(
            """CREATE TABLE User (
            username TEXT,
            password TEXT NOT NULL,
            salt TEXT NOT NULL,
            token TEXT,
            PRIMARY KEY(username)
        ) WITHOUT ROWID"""
        )
        # self-author and self-pub
        await cursor.execute(
            """CREATE TABLE Source (
            owner TEXT,
            key TEXT,
            values_json TEXT,
            task_json TEXT,
            due INTEGER NOT NULL,
            FOREIGN KEY(owner) REFERENCES User(username),
            PRIMARY KEY(owner, key)
        ) WITHOUT ROWID"""
        )
        await cursor.execute(
            """CREATE TABLE Author (
            owner TEXT,
            source TEXT,
            path TEXT,
            full_name TEXT NOT NULL,
            id TEXT,
            first_name TEXT,
            last_name TEXT,
            extra_json TEXT,
            FOREIGN KEY(owner) REFERENCES User(username),
            FOREIGN KEY(owner, source) REFERENCES Source(owner, key),
            PRIMARY KEY(owner, source, path)
        ) WITHOUT ROWID"""
        )
        await cursor.execute(
            """CREATE TABLE Publication (
            owner TEXT,
            source TEXT,
            path TEXT,
            by_self INTEGER NOT NULL,
            name TEXT NOT NULL,
            id TEXT,
            year INTEGER,
            ref TEXT,
            extra_json TEXT,
            FOREIGN KEY(owner) REFERENCES User(username),
            FOREIGN KEY(owner, source) REFERENCES Source(owner, key),
            PRIMARY KEY(owner, source, path)
        ) WITHOUT ROWID"""
        )
        await cursor.execute(
            """CREATE TABLE PublicationAuthors (
            owner TEXT,
            source TEXT,
            pub_path TEXT,
            author_path TEXT,
            FOREIGN KEY(owner) REFERENCES User(username),
            FOREIGN KEY(owner, source) REFERENCES Source(owner, key),
            FOREIGN KEY(owner, source, pub_path) REFERENCES Publication(owner, source, path),
            FOREIGN KEY(owner, source, author_path) REFERENCES Author(owner, source, path),
            PRIMARY KEY(owner, source, pub_path, author_path)
        ) WITHOUT ROWID"""
        )
        await cursor.execute(
            """CREATE TABLE Cites (
            owner TEXT,
            source TEXT,
            pub_path TEXT,
            cited_by TEXT,
            FOREIGN KEY(owner) REFERENCES User(username),
            FOREIGN KEY(owner, source) REFERENCES Source(owner, key),
            FOREIGN KEY(owner, source, pub_path) REFERENCES Publication(owner, source, path),
            FOREIGN KEY(owner, source, cited_by) REFERENCES Publication(owner, source, path),
            PRIMARY KEY(owner, source, pub_path, cited_by)
        ) WITHOUT ROWID"""
        )
        await cursor.execute("INSERT INTO Version VALUES (?)", (DB_VERSION,))
        # TODO merges

    @_transaction
    async def _upgrade_tables(self, cursor=None):
        pass

    # Convenience

    def _select(self, table: type, query: str = "", *args) -> Select:
        return Select(self._db, table, query, args)

    async def _select_one(self, table: type, query: str = "", *args):
        async with Select(self._db, table, query, args) as select:
            return await select.one()

    @_transaction
    async def _insert(self, *tuples, cursor=None):
        for tup in tuples:
            fields = ",".join("?" * len(tup))
            await self._db.execute(
                f"INSERT INTO {tup.__class__.__name__} VALUES ({fields})", tup
            )

    @_transaction
    async def _execute(self, query, *args, cursor=None):
        await cursor.execute(query, args)
        return cursor.rowcount

    # Public methods

    async def register_user(
        self, *, username: str, password: str, salt: str, token: str
    ):
        await self._insert(
            User(username=username, password=password, salt=salt, token=token,)
        )

    async def login_user(self, *, username, token):
        await self._execute(
            "UPDATE User SET token = ? WHERE username = ?", token, username
        )

    async def logout_user(self, *, username):
        await self._execute("UPDATE User SET token = null WHERE username = ?", username)

    async def delete_user(self, *, username):
        rowcount = await self._execute("DELETE FROM User WHERE username = ?", username)
        return rowcount != 0

    async def update_user_password(self, *, username, password, salt):
        await self._execute(
            "UPDATE User SET password = ?, salt = ? WHERE username = ?",
            password,
            salt,
            username,
        )

    async def get_user_password(self, *, username: str):
        user = await self._select_one(User, "WHERE username = ?", username)
        return (user.password, user.salt) if user else None

    async def get_username(self, *, token: str):
        user = await self._select_one(User, "WHERE token = ?", token)
        return user.username if user else None

    async def has_user(self, *, username: str):
        user = await self._select_one(User, "WHERE username = ?", username)
        return user is not None

    async def next_source_task(self):
        return await self._select_one(Source, "ORDER BY due ASC LIMIT 1")

    async def get_source_values(self, username):
        result = {}
        async with self._select(Source, "WHERE owner = ?", username) as select:
            async for source in select:
                result[source.key] = json.loads(source.values_json)
        return result

    @_transaction
    async def update_source_values(self, username, sources, *, cursor=None):
        for source, fields in sources.items():
            values_json = json.dumps(fields)
            rowcount = await self._execute(
                "UPDATE Source SET values_json = ?, due = 0 WHERE owner = ? AND key = ?",
                values_json,
                username,
                source,
                cursor=cursor,
            )
            if rowcount == 0:
                await self._insert(
                    Source(
                        owner=username,
                        key=source,
                        values_json=values_json,
                        task_json=None,
                        due=0,
                    ),
                    cursor=cursor,
                )

    @_transaction
    async def save_crawler_step(self, source, step, *, cursor=None):
        await self._insert(
            *(
                Author(
                    owner=source.owner,
                    source=source.key,
                    path=author.unique_path_name(),
                    full_name=author.full_name,
                    id=author.id,
                    first_name=author.first_name,
                    last_name=author.last_name,
                    extra_json=json.dumps(author.extra),
                )
                for author in step.authors
            ),
            cursor=cursor,
        )
        # TODO what happens if one of the citations is our own?
        # probably sqlite3.IntegrityError: UNIQUE constraint failed
        await self._insert(
            *(
                Publication(
                    owner=source.owner,
                    source=source.key,
                    path=pub.unique_path_name(),
                    by_self=by_self,
                    name=pub.name,
                    id=pub.id,
                    year=pub.year,
                    ref=pub.ref,
                    extra_json=json.dumps(pub.extra),
                )
                for pub, by_self in _adapt_step_publications(step)
            ),
            cursor=cursor,
        )
        for pub, _ in _adapt_step_publications(step):
            await self._insert(
                *(
                    PublicationAuthors(
                        owner=source.owner,
                        source=source.key,
                        pub_path=pub.unique_path_name(),
                        author_path=author_path,
                    )
                    for author_path in pub.authors
                ),
                cursor=cursor,
            )
        for cites_pub_id, citations in step.citations.items():
            # TODO bad (maybe the step should have a method to get all the tuples to insert?)
            pub_path = StepPublication(name="", id=cites_pub_id).unique_path_name()
            await self._insert(
                *(
                    Cites(
                        owner=source.owner,
                        source=source.key,
                        pub_path=pub_path,
                        cited_by=cit.unique_path_name(),
                    )
                    for cit in citations
                ),
                cursor=cursor,
            )
        await self._execute(
            "UPDATE Source SET task_json = ?, due = ? WHERE owner = ? AND key = ?",
            step.stage_as_json(),
            step.due(),
            source.owner,
            source.key,
            cursor=cursor,
        )


if __name__ == "__main__":

    async def main():
        async with Database("test.db") as db:
            # await db.register_user(username='a', password='b', salt='c', token='d')
            print(await db.get_username(token="e"))
            pass

    import asyncio

    asyncio.run(main())
