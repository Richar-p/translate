#
# Copyright 2009, 2013 Zuza Software Foundation
# Copyright 2013 F Wolff
#
# This file is part of translate.
#
# translate is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# translate is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

"""Module to provide a translation memory database."""

import contextlib
import logging
import math
import operator
import re
import threading
import time
from sqlite3 import dbapi2

from translate.lang import data
from translate.search.lshtein import LevenshteinComparer

logger = logging.getLogger(__name__)
STRIP_REGEXP = re.compile(r"\W", re.UNICODE)


class LanguageError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)


class TMDB:
    _tm_dbs = {}

    def __init__(self, db_file, max_candidates=3, min_similarity=75, max_length=1000):
        self.max_candidates = max_candidates
        self.min_similarity = min_similarity
        self.max_length = max_length

        if not isinstance(db_file, str):
            db_file = str(db_file)  # don't know which encoding
        self.db_file = db_file
        # share connections to same database file between different instances
        if db_file not in self._tm_dbs:
            self._tm_dbs[db_file] = {}
        self._tm_db = self._tm_dbs[db_file]

        # FIXME: do we want to do any checks before we initialize the DB?
        self.init_database()
        self.fulltext = False
        self.init_fulltext()

        self.comparer = LevenshteinComparer(self.max_length)

        self.preload_db()

    def _get_connection(self, index):
        current_thread = threading.current_thread()
        if current_thread not in self._tm_db:
            connection = dbapi2.connect(self.db_file)
            cursor = connection.cursor()
            self._tm_db[current_thread] = (connection, cursor)
        return self._tm_db[current_thread][index]

    connection = property(lambda self: self._get_connection(0))
    cursor = property(lambda self: self._get_connection(1))

    def init_database(self):
        """Creates database tables and indices."""
        script = """
CREATE TABLE IF NOT EXISTS sources (
       sid INTEGER PRIMARY KEY AUTOINCREMENT,
       text VARCHAR NOT NULL,
       context VARCHAR DEFAULT NULL,
       lang VARCHAR NOT NULL,
       length INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS sources_context_idx ON sources (context);
CREATE INDEX IF NOT EXISTS sources_lang_idx ON sources (lang);
CREATE INDEX IF NOT EXISTS sources_length_idx ON sources (length);
CREATE UNIQUE INDEX IF NOT EXISTS sources_uniq_idx ON sources (text, context, lang);

CREATE TABLE IF NOT EXISTS targets (
       tid INTEGER PRIMARY KEY AUTOINCREMENT,
       sid INTEGER NOT NULL,
       text VARCHAR NOT NULL,
       lang VARCHAR NOT NULL,
       time INTEGER DEFAULT NULL,
       FOREIGN KEY (sid) references sources(sid)
);
CREATE INDEX IF NOT EXISTS targets_sid_idx ON targets (sid);
CREATE INDEX IF NOT EXISTS targets_lang_idx ON targets (lang);
CREATE INDEX IF NOT EXISTS targets_time_idx ON targets (time);
CREATE UNIQUE INDEX IF NOT EXISTS targets_uniq_idx ON targets (sid, text, lang);
"""

        try:
            self.cursor.executescript(script)
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def init_fulltext(self):
        """Detects if fts3 fulltext indexing module exists, initializes fulltext table if it does."""
        # HACKISH: no better way to detect fts3 support except trying to
        # construct a dummy table?!
        try:
            script = """
DROP TABLE IF EXISTS test_for_fts3;
CREATE VIRTUAL TABLE test_for_fts3 USING fts3;
DROP TABLE test_for_fts3;
"""
            self.cursor.executescript(script)
            logger.debug("fts3 supported")
            # for some reason CREATE VIRTUAL TABLE doesn't support IF NOT
            # EXISTS syntax check if fulltext index table exists manually
            self.cursor.execute(
                "SELECT name FROM sqlite_master WHERE name = 'fulltext'"
            )
            if not self.cursor.fetchone():
                # create fulltext index table, and index all strings in sources
                script = """
CREATE VIRTUAL TABLE fulltext USING fts3(text);
"""
                logger.debug("fulltext table not exists, creating")
                self.cursor.executescript(script)
                logger.debug("created fulltext table")
            else:
                logger.debug("fulltext table already exists")

            # create triggers that would sync sources table with fulltext index
            script = """
INSERT INTO fulltext (rowid, text) SELECT sid, text FROM sources WHERE sid NOT IN (SELECT rowid FROM fulltext);
CREATE TRIGGER IF NOT EXISTS sources_insert_trig AFTER INSERT ON sources FOR EACH ROW
BEGIN
    INSERT INTO fulltext (docid, text) VALUES (NEW.sid, NEW.text);
END;
CREATE TRIGGER IF NOT EXISTS sources_update_trig AFTER UPDATE OF text ON sources FOR EACH ROW
BEGIN
    UPDATE fulltext SET text = NEW.text WHERE docid = NEW.sid;
END;
CREATE TRIGGER IF NOT EXISTS sources_delete_trig AFTER DELETE ON sources FOR EACH ROW
BEGIN
    DELETE FROM fulltext WHERE docid = OLD.sid;
END;
"""
            self.cursor.executescript(script)
            self.connection.commit()
            logger.debug("created fulltext triggers")
            self.fulltext = True

        except dbapi2.OperationalError:
            self.fulltext = False
            logger.exception("failed to initialize fts3 support")
            script = """
DROP TRIGGER IF EXISTS sources_insert_trig;
DROP TRIGGER IF EXISTS sources_update_trig;
DROP TRIGGER IF EXISTS sources_delete_trig;
"""
            self.cursor.executescript(script)

    def preload_db(self):
        """
        Ugly hack to force caching of sqlite db file in memory for improved
        performance.
        """
        if self.fulltext:
            query = """SELECT COUNT(*) FROM sources s JOIN fulltext f ON s.sid = f.docid JOIN targets t on s.sid = t.sid"""
        else:
            query = """SELECT COUNT(*) FROM sources s JOIN targets t on s.sid = t.sid"""
        self.cursor.execute(query)
        (numrows,) = self.cursor.fetchone()
        logger.debug("tmdb has %d records", numrows)
        return numrows

    def add_unit(self, unit, source_lang=None, target_lang=None, commit=True):
        """Inserts unit in the database."""
        # TODO: is that really the best way to handle unspecified
        # source and target languages? what about conflicts between
        # unit attributes and passed arguments
        if unit.getsourcelanguage():
            source_lang = unit.getsourcelanguage()
        if unit.gettargetlanguage():
            target_lang = unit.gettargetlanguage()

        if not source_lang:
            raise LanguageError("undefined source language")
        if not target_lang:
            raise LanguageError("undefined target language")

        unitdict = {
            "source": unit.source,
            "target": unit.target,
            "context": unit.getcontext(),
        }
        self.add_dict(unitdict, source_lang, target_lang, commit)

    def add_dict(self, unit, source_lang, target_lang, commit=True):
        """Inserts units represented as dictionaries in database."""
        source_lang = data.normalize_code(source_lang)
        target_lang = data.normalize_code(target_lang)
        try:
            try:
                self.cursor.execute(
                    "INSERT INTO sources (text, context, lang, length) VALUES(?, ?, ?, ?)",
                    (unit["source"], unit["context"], source_lang, len(unit["source"])),
                )
                sid = self.cursor.lastrowid
            except dbapi2.IntegrityError:
                # source string already exists in db, run query to find sid
                self.cursor.execute(
                    "SELECT sid FROM sources WHERE text=? AND context=? and lang=?",
                    (unit["source"], unit["context"], source_lang),
                )
                sid = self.cursor.fetchone()
                (sid,) = sid
            # target string already exists in db, do nothing
            with contextlib.suppress(dbapi2.IntegrityError):
                # FIXME: get time info from translation store
                # FIXME: do we need so store target length?
                self.cursor.execute(
                    "INSERT INTO targets (sid, text, lang, time) VALUES (?, ?, ?, ?)",
                    (sid, unit["target"], target_lang, int(time.time())),
                )

            if commit:
                self.connection.commit()
        except Exception:
            if commit:
                self.connection.rollback()
            raise

    def add_store(self, store, source_lang, target_lang, commit=True):
        """Insert all units in store in database."""
        count = 0
        for unit in store.units:
            if unit.istranslatable() and unit.istranslated():
                self.add_unit(unit, source_lang, target_lang, commit=False)
                count += 1
        if commit:
            self.connection.commit()
        return count

    def add_list(self, units, source_lang, target_lang, commit=True):
        """
        Insert all units in list into the database, units are represented as
        dictionaries.
        """
        count = 0
        for unit in units:
            self.add_dict(unit, source_lang, target_lang, commit=False)
            count += 1
        if commit:
            self.connection.commit()
        return count

    def translate_unit(self, unit_source, source_langs, target_langs):
        """Return TM suggestions for unit_source."""
        if isinstance(source_langs, list):
            source_langs = [data.normalize_code(lang) for lang in source_langs]
            source_langs = ",".join(source_langs)
        else:
            source_langs = data.normalize_code(source_langs)
        if isinstance(target_langs, list):
            target_langs = [data.normalize_code(lang) for lang in target_langs]
            target_langs = ",".join(target_langs)
        else:
            target_langs = data.normalize_code(target_langs)

        minlen = min_levenshtein_length(len(unit_source), self.min_similarity)
        maxlen = max_levenshtein_length(
            len(unit_source), self.min_similarity, self.max_length
        )

        # split source into words, remove punctuation and special
        # chars, keep words that are at least 3 chars long
        unit_words = STRIP_REGEXP.sub(" ", unit_source).split()
        unit_words = list(filter(lambda word: len(word) > 2, unit_words))

        if self.fulltext and len(unit_words) > 3:
            logger.debug("fulltext matching")
            query = """SELECT s.text, t.text, s.context, s.lang, t.lang FROM sources s JOIN targets t ON s.sid = t.sid JOIN fulltext f ON s.sid = f.docid
                       WHERE s.lang IN (?) AND t.lang IN (?) AND s.length BETWEEN ? AND ?
                       AND fulltext MATCH ?"""
            search_str = " OR ".join(unit_words)
            self.cursor.execute(
                query, (source_langs, target_langs, minlen, maxlen, search_str)
            )
        else:
            logger.debug("nonfulltext matching")
            query = """SELECT s.text, t.text, s.context, s.lang, t.lang FROM sources s JOIN targets t ON s.sid = t.sid
            WHERE s.lang IN (?) AND t.lang IN (?)
            AND s.length >= ? AND s.length <= ?"""
            self.cursor.execute(query, (source_langs, target_langs, minlen, maxlen))

        results = []
        for row in self.cursor:
            quality = self.comparer.similarity(unit_source, row[0], self.min_similarity)
            if quality >= self.min_similarity:
                results.append(
                    {
                        "source": row[0],
                        "target": row[1],
                        "context": row[2],
                        "quality": quality,
                    }
                )
        results.sort(key=operator.itemgetter("quality"), reverse=True)
        results = results[: self.max_candidates]
        logger.debug("results: %s", str(results))
        return results


def min_levenshtein_length(length, min_similarity):
    return math.ceil(max(length * (min_similarity / 100.0), 2))


def max_levenshtein_length(length, min_similarity, max_length):
    return math.floor(min(length / (min_similarity / 100.0), max_length))
