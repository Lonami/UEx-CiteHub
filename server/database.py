from aiosqlite import Connection
from collections import namedtuple
from dataclasses import asdict
import itertools
import sqlite3
import csv
import zipfile
import io
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
Merge = namedtuple("Merge", "owner source_a source_b pub_a pub_b similarity")


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
    # Go over citations first so that if any of the self publications was also
    # present as a a citation, it will be replaced but marked as `by_self`.
    for citations in step.citations.values():
        for cit in citations:
            yield cit, 0

    for pub in step.self_publications:
        yield pub, 1


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

    async def all(self):
        result = []
        async for item in self:
            result.append(item)
        return result

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
        await cursor.execute(
            """CREATE TABLE Source (
            owner TEXT,
            key TEXT,
            values_json TEXT,
            task_json TEXT,
            due INTEGER NOT NULL,
            FOREIGN KEY(owner) REFERENCES User(username) ON DELETE CASCADE,
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
            FOREIGN KEY(owner) REFERENCES User(username) ON DELETE CASCADE,
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
            FOREIGN KEY(owner) REFERENCES User(username) ON DELETE CASCADE,
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
            FOREIGN KEY(owner) REFERENCES User(username) ON DELETE CASCADE,
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
            FOREIGN KEY(owner) REFERENCES User(username) ON DELETE CASCADE,
            FOREIGN KEY(owner, source) REFERENCES Source(owner, key),
            FOREIGN KEY(owner, source, pub_path) REFERENCES Publication(owner, source, path),
            FOREIGN KEY(owner, source, cited_by) REFERENCES Publication(owner, source, path),
            PRIMARY KEY(owner, source, pub_path, cited_by)
        ) WITHOUT ROWID"""
        )
        await cursor.execute(
            """CREATE TABLE Merge (
            owner TEXT,
            source_a TEXT,
            source_b TEXT,
            pub_a TEXT,
            pub_b TEXT,
            similarity REAL NOT NULL,
            FOREIGN KEY(owner) REFERENCES User(username) ON DELETE CASCADE,
            FOREIGN KEY(owner, source_a) REFERENCES Source(owner, key),
            FOREIGN KEY(owner, source_b) REFERENCES Source(owner, key),
            FOREIGN KEY(owner, source_a, pub_a) REFERENCES Publication(owner, source, path),
            FOREIGN KEY(owner, source_b, pub_b) REFERENCES Publication(owner, source, path),
            PRIMARY KEY(owner, source_a, source_b, pub_a, pub_b)
        ) WITHOUT ROWID"""
        )
        await cursor.execute("INSERT INTO Version VALUES (?)", (DB_VERSION,))

    @_transaction
    async def _upgrade_tables(self, cursor=None):
        pass

    # Convenience

    def _select(self, table: type, query: str = "", *args) -> Select:
        return Select(self._db, table, query, args)

    async def _select_one(self, table: type, query: str = "", *args):
        async with Select(self._db, table, query, args) as select:
            return await select.one()

    async def _select_all(self, table: type, query: str = "", *args):
        async with Select(self._db, table, query, args) as select:
            return await select.all()

    @_transaction
    async def _insert(self, *tuples, cursor=None):
        for tup in tuples:
            fields = ",".join("?" * len(tup))
            await self._db.execute(
                f"INSERT INTO {tup.__class__.__name__} VALUES ({fields})", tup
            )

    @_transaction
    async def _insert_or_replace(self, *tuples, cursor=None):
        for tup in tuples:
            fields = ",".join("?" * len(tup))
            await self._db.execute(
                f"INSERT OR REPLACE INTO {tup.__class__.__name__} VALUES ({fields})",
                tup,
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
        # Use `_insert_or_replace` under the premise that sources may omit
        # information entirely, but not provide less information about what
        # is known (so replacing old data won't produce any loss).
        await self._insert_or_replace(
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
        await self._insert_or_replace(
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
            await self._insert_or_replace(
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
            await self._insert_or_replace(
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

    async def get_usernames(self):
        usernames = []
        async with self._select(User) as select:
            async for user in select:
                usernames.append(user.username)
        return usernames

    async def get_source_publications(self, username, source):
        return await self._select_all(
            Publication, "WHERE owner = ? AND source = ?", username, source
        )

    @_transaction
    async def save_merges(self, username, merges, *, cursor=None):
        await self._execute(
            "DELETE FROM Merge WHERE owner = ?", username, cursor=cursor
        )
        await self._insert(
            *(
                Merge(
                    owner=username,
                    source_a=m.source_a,
                    source_b=m.source_b,
                    pub_a=m.pub_a,
                    pub_b=m.pub_b,
                    similarity=m.similarity,
                )
                for m in merges
            ),
            cursor=cursor,
        )

    async def get_publications(self, username):
        # TODO merge publications and cites and other stats like author count
        # TODO this should be smarter and if any has missing data (e.g. year) use a different source
        publications = {}
        async with self._db.execute(
            """
            SELECT
                p.source,
                p.path,
                p.name,
                p.year,
                p.ref,
                a.full_name,
                c.cited_by
            FROM Publication AS p
            JOIN PublicationAuthors AS pa ON (
                p.owner = pa.owner
                AND p.source = pa.source
                AND p.path = pa.pub_path
            )
            JOIN Author AS a ON (
                p.owner = a.owner
                AND p.source = a.source
                AND pa.author_path = a.path
            )
            LEFT JOIN Cites AS c ON (
                p.owner = c.owner
                AND p.source = c.source
                AND p.path = c.pub_path
            )
            WHERE
                p.owner = ?
                AND p.by_self = 1
        """,
            (username,),
        ) as cursor:
            async for (
                source,
                pub_path,
                pub_name,
                year,
                ref,
                author_name,
                cit_path,
            ) in cursor:
                if pub_path in publications:
                    publications[pub_path]["sources"][source] = ref
                    publications[pub_path]["author_names"].add(author_name)
                    publications[pub_path]["cites"].add(cit_path)
                else:
                    publications[pub_path] = {
                        "sources": {source: ref},
                        "name": pub_name,
                        "author_names": {author_name},
                        "cites": {cit_path},
                        "year": year,
                    }

        return [
            {
                "sources": [{"key": k, "ref": v} for k, v in p["sources"].items()],
                "name": p["name"],
                "authors": [{"full_name": a} for a in p["author_names"]],
                "cites": sum(1 for c in p["cites"] if c),
                "year": p["year"],
            }
            for p in publications.values()
        ]

    async def _export_table_as_csv(self, table, owner, fields):
        fields = fields.split()
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer)
        writer.writerow(fields)
        async with self._select(table, "WHERE owner = ?", owner) as select:
            async for row in select:
                writer.writerow(getattr(row, field) for field in fields)
        buffer.flush()
        return buffer.getvalue()

    async def export_data_as_zip(self, username):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            zf.writestr(
                "sources.csv",
                await self._export_table_as_csv(Source, username, "key values_json"),
            )
            zf.writestr(
                "authors.csv",
                await self._export_table_as_csv(
                    Author,
                    username,
                    "source path full_name id first_name last_name extra_json",
                ),
            )
            zf.writestr(
                "publications.csv",
                await self._export_table_as_csv(
                    Publication,
                    username,
                    "source path by_self name id year ref extra_json",
                ),
            )
            zf.writestr(
                "publication-authors.csv",
                await self._export_table_as_csv(
                    PublicationAuthors, username, "source pub_path author_path"
                ),
            )
            zf.writestr(
                "cites.csv",
                await self._export_table_as_csv(
                    Cites, username, "source pub_path cited_by"
                ),
            )
            zf.writestr(
                "merges.csv",
                await self._export_table_as_csv(
                    Merge, username, "source_a source_b pub_a pub_b similarity"
                ),
            )
        return buffer.getvalue()


if __name__ == "__main__":

    async def main():
        async with Database("../uex.db") as db:
            await db.get_publications("admin")

    import asyncio

    asyncio.run(main())
