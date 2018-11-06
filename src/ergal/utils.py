""" ERGAL utilities. """

import os
import json
import hashlib
import sqlite3
from warnings import warn

from ergal.exceptions import HandlerException, ProfileException

import requests


class Handler:
    """ Handles API profiles. """
    def __init__(self, profile):
        """ Initialize the Handler class.

        Handler handles the parsing of API responses according to
        the given API profile.

        Arguments:
            Profile:profile -- an API Profile object.
        
        """
        if not profile:
            raise HandlerException(self, 'init:no profile')

        self.profile = profile

        if self.profile.auth['method'] == 'basic':
            self.auth_method = 'basic'
        elif self.profile.auth['method'] == 'key':
            self.auth_method = 'key'
        else:
            raise HandlerException(profile, 'init: unsupported auth type')
    
    def call(self, endpoint):
        """ Call an endpoint.

        An endpoint dict is submitted from the API profile.
        
        """


class Profile:
    """ Manages API profiles. """
    def __init__(self, name, base='', test=False):
        """ Initialize Profiler class.

        Profiler handles the creation and storage of API profiles.
        These objects are created and stored in SQLite database.
        
        Arguments:
            str:name -- the name of the profile
        
        Keyword Arguments:
            str:base -- the API's base URL
            bool:test -- 
                tells the class to create a test database
                that will be deleted post-tests
        
        """
        # check args
        if type(name) != str:
            raise ProfileException(self, 'init: invalid name')
        elif type(base) != str:
            raise ProfileException(self, 'init: invalid base')

        # validate base
        if base[:8] not in 'https://':
            warn('base argument rejected: invalid URL.')
            base = ''
        elif ' ' in base or '.' not in base:
            warn('base argument rejected: invalid URL.')
            base = ''
        elif base[-1:] == '/':
            warn('base argument altered: trailing /')
            base = base[:-1]

        self.id = hashlib.sha256(bytes(name, 'utf-8')).hexdigest()[::2]
        self.name = name
        self.base = base
        self.auth = {}
        self.endpoints = {}

        # create db/table if nonexistent
        if not test:
            self.db = sqlite3.connect('ergal.db')
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS Profile (
                    id          TEXT    NOT NULL,
                    name        TEXT    NOT NULL,
                    base        TEXT    NOT NULL,
                    auth        TEXT,
                    endpoints   TEXT,

                    PRIMARY KEY(id)
                )
            """)
            self.cursor = self.db.cursor()
        else:
            self.db = sqlite3.connect('ergal_test.db')
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS Profile (
                    id          TEXT    NOT NULL,
                    name        TEXT    NOT NULL,
                    base        TEXT    NOT NULL,
                    auth        TEXT,
                    endpoints   TEXT,

                    PRIMARY KEY(id)
                )
            """)
            self.cursor = self.db.cursor()

        # create record if nonexistent in database
        try:
            self._get()
        except ProfileException as e:
            if str(e) == 'get: no matching record':
                self._create()
            else:
                raise ProfileException(self, 'get: selection failed')
    
    def _get(self):
        """ Get the record from the Profile table.

        Uses the instance's ID value to pull the corresponding
        record from the database file. If no record is found, 
        ProfileException is raised, allowing __init__ to insert the record.
        
        """
        if not self.id:
            raise ProfileException(self, 'get: insufficient info')

        sql = """
            SELECT *
            FROM Profile
            WHERE id = ?
        """
        try:
            self.cursor.execute(sql, (self.id,))
        except sqlite3.DatabaseError:
            raise ProfileException(self, 'get: selection failed')
        else:
            record = self.cursor.fetchone()
            if record:
                self.id = record[0]
                self.name = record[1]
                self.base = record[2]
                if record[3]:
                    self.auth = json.loads(record[3])
                else:
                    self.auth = ''
                if record[4]:
                    self.endpoints = json.loads(record[4])
                else:
                    self.endpoints = ''
            else:
                raise ProfileException(self, 'get: no matching record')

    def _create(self):
        """ Create a record in the Profile table.

        Using only the current instance's id, name, and base,
        a row is inserted into the Profile table.
        
        """
        if not self.id or not self.name:
            raise ProfileException(self, 'create: insufficient info')

        sql = """
            INSERT INTO Profile
            (id, name, base)
            VALUES (?, ?, ?)
        """
        try:
            with self.db:
                self.cursor.execute(sql, (self.id, self.name, self.base,))
        except sqlite3.DatabaseError:
            raise ProfileException(self, 'create: insertion failed')
        else:
            return "Profile for {name} created at {id}.".format(
                name=self.name,
                id=self.id)
        
    def set_auth(self, method, **kwargs):
        """ Set authentication details.

        Using the current instance's id and auth dict,
        the auth field is updated in the respective row.

        Arguments:
            str:method -- a supported auth method

        Keyword Arguments:
            str:key -- an authentication key
            str:name -- a name for the given key
            str:username -- a username
            str:password -- a password
        
        """
        if not method:
            raise ProfileException(self, 'add_auth: null method')
        elif type(method) != str:
            raise ProfileException(self, 'add_auth: invalid method type')
        
        if method == 'basic':
            try:
                auth = {
                    'method': method,
                    'username': kwargs['username'],
                    'password': kwargs['password']}
            except:
                raise ProfileException(self, 'add_auth: missing params')
        elif method == 'key-header':
            try:
                auth = {
                    'method': method,
                    'key': kwargs['key'],
                    'name': kwargs['name']}
            except:
                raise ProfileException(self, 'add_auth: missing params')
        elif method == 'key-query':
            try:
                auth = {
                    'method': method,
                    'key': kwargs['key'],
                    'name': kwargs['name']}
            except:
                raise ProfileException(self, 'add_auth: missing params')
        else:
            raise ProfileException(self, 'add_auth: unsupported')

        self.auth = auth
        auth_str = json.dumps(self.auth)
        sql = """
            UPDATE Profile
            SET auth = ?
            WHERE id = ?
        """
        try:
            with self.db:
                self.cursor.execute(sql, (auth_str, self.id,))
        except sqlite3.DatabaseError:
            raise ProfileException(self, 'add_auth: update failed')
        else:
            return "Authentication details for {name} set at {id}".format(
                name=self.name,
                id=self.id)
        
    def add_endpoint(self, name, path=None, method=None):
        """ Add an endpoint. 
        
        Using the current instance's id and an endpoint
        dict passed as an argument, the given endpoint is added
        to the instance's endpoints list, which is then set
        via an update to the respective record.

        Arguments:
            str:name -- a name describing the given endpoint

        Keyword Arguments:
            str:path -- the given path to the API endpoint
            str:method -- the method assigned to the given endpoint

        """
        if not name or not path or not method:
            raise ProfileException(self, 'add_endpoint: incomplete args')
        elif type(name) != str:
            raise ProfileException(self, 'add_endpoint: invalid input')
        elif type(path) != str:
            raise ProfileException(self, 'add_endpoint: invalid path')
        elif type(method) != str:
            raise ProfileException(self, 'add_endpoint: invalid method')

        if path[-1] == '/':
            warn('endpoint altered: trailing /')
            path = path[:-1]
        if path[0] != '/':
            warn('endpoint altered: absent root /')
            path = '/' + path
        if ' ' in path:
            warn('endpoint altered: whitespace present')
            path = path.replace(' ', '')

        endpoint = {
            'path': path,
            'method': method}
        
        self.endpoints[name] = endpoint
        endpoints_str = json.dumps(self.endpoints)
        sql = """
            UPDATE Profile
            SET endpoints = ?
            WHERE id = ?
        """
        try:
            with self.db:
                self.cursor.execute(sql, (endpoints_str, self.id,))
        except sqlite3.DatabaseError:
            raise ProfileException(self, 'add_endpoint: update failed')
        else:
            return "Endpoint {path} for {name} added at {id}.".format(
                path=path,
                name=self.name,
                id=self.id)

