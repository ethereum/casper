# -*- coding: utf8 -*-

from devp2p.service import BaseService
from ethereum.db import BaseDB
from ethereum.slogging import get_logger
from leveldb_service import LevelDBService

log = get_logger('db')


class DBService(BaseDB, BaseService):

    name = 'db'
    default_config = dict()

    def __init__(self, app):
        super(DBService, self).__init__(app)
        self.db_service = LevelDBService(app)

    def start(self):
        return self.db_service.start()

    def _run(self):
        return self.db_service._run()

    def get(self, key):
        return self.db_service.get(key)

    def put(self, key, value):
        return self.db_service.put(key, value)

    def commit(self):
        return self.db_service.commit()

    def delete(self, key):
        return self.db_service.delete(key)

    def __contains__(self, key):
        return key in self.db_service

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.db_service == other.db_service

    def __repr__(self):
        return repr(self.db_service)

    def inc_refcount(self, key, value):
        self.put(key, value)

    def dec_refcount(self, key):
        pass

    def revert_refcount_changes(self, epoch):
        pass

    def commit_refcount_changes(self, epoch):
        pass

    def cleanup(self, epoch):
        pass

    def put_temporarily(self, key, value):
        self.inc_refcount(key, value)
        self.dec_refcount(key)
