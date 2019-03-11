"""
ergal.utils
~~~~~~~~~~~

This module implements the utility methods used by the
Profile interface.

:copyright: (c) 2018 by Elliott Maguire
"""

import json
import types
import sqlite3

import xmltodict


def get_db(test=False):
    """ Get/create a database connection.

    If a local ergal.db file exists, a connection
    is established and returned, otherwise a new
    database is created and the connection is returned.

    :param test: (optional) determines whether or not a test database
                            should be created.
    """
    file = 'ergal_test.db' if test else 'ergal.db'
    db = sqlite3.connect(file)
    cursor = db.cursor()

    db.execute("""
        CREATE TABLE IF NOT EXISTS Profile (
            id          TEXT    NOT NULL,
            name        TEXT    NOT NULL,
            base        TEXT    NOT NULL,
            auth        TEXT,
            endpoints   TEXT,

            PRIMARY KEY(id))""")

    return db, cursor


def parse(response, targets):
    """ Parse response data.

    :param response: a requests.Response object
    :param targets: a list of data targets
    """
    targets = json.loads(targets) if targets else None

    try:
        data = json.loads(response.text)
    except json.JSONDecodeError:
        data = xmltodict.parse(response.text)

    if type(data) is list:
        data = {'data': data}

    output = {}
    def search(d):
        for k, v in d.items():
            if k in targets:
                output[k] = None
                yield v
            elif type(v) is dict:
                for i in v:
                    if i in targets:
                        output[i] = None
                        yield v[i]
                    elif type(v[i]) is dict:
                        for j in search(i):
                            output[j] = None
                            yield j

    for k, v in zip(output, [i for i in search(data)]):
        output[k] = v

    return output
