from aiosqlite import Connection
from collections import namedtuple
import sqlite3
import functools


DB_VERSION = 1
Version = namedtuple("Version", "version")
User = namedtuple("User", "username password salt token")


def _transaction(func):
    @functools.wraps(func)
    async def wrapped(self, *args, **kwargs):
        async with self._db.execute("BEGIN") as cursor:
            try:
                await func(self, *args, cursor=cursor, **kwargs)
            except sqlite3.Error:
                await cursor.execute("ROLLBACK")
                raise
            else:
                await cursor.execute("COMMIT")

    return wrapped


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
            due INTEGER,
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
            FOREIGN KEY(source) REFERENCES Source(key),
            PRIMARY KEY(owner, source, path)
        ) WITHOUT ROWID"""
        )
        await cursor.execute(
            """CREATE TABLE Publication (
            owner TEXT,
            source TEXT,
            path TEXT,
            name TEXT NOT NULL,
            id TEXT,
            year INTEGER,
            ref TEXT,
            extra_json TEXT,
            FOREIGN KEY(owner) REFERENCES User(username),
            FOREIGN KEY(source) REFERENCES Source(key),
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
            FOREIGN KEY(source) REFERENCES Source(key),
            FOREIGN KEY(pub_path) REFERENCES Publication(path),
            FOREIGN KEY(author_path) REFERENCES Author(path),
            PRIMARY KEY(owner, source, pub_path, author_path)
        ) WITHOUT ROWID"""
        )
        await cursor.execute(
            """CREATE TABLE Cites (
            owner TEXT,
            source TEXT,
            pub TEXT,
            cited_by TEXT,
            FOREIGN KEY(owner) REFERENCES User(username),
            FOREIGN KEY(source) REFERENCES Source(key),
            FOREIGN KEY(pub) REFERENCES Publication(path),
            FOREIGN KEY(cited_by) REFERENCES Publication(path),
            PRIMARY KEY(owner, source, pub, cited_by)
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


if __name__ == "__main__":

    async def main():
        async with Database("test.db") as db:
            # await db.register_user(username='a', password='b', salt='c', token='d')
            print(await db.get_username(token="e"))
            pass

    import asyncio

    asyncio.run(main())
