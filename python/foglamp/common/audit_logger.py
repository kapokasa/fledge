# -*- coding: utf-8 -*-

# FOGLAMP_BEGIN
# See: http://foglamp.readthedocs.io/
# FOGLAMP_END

import json
from foglamp.common.storage_client.payload_builder import PayloadBuilder
from foglamp.common.storage_client.storage_client import StorageClient

from foglamp.common import logger

__author__ = "Mark Riddoch"
__copyright__ = "Copyright (c) 2018 OSIsoft, LLC"
__license__ = "Apache 2.0"
__version__ = "${VERSION}"


_logger = logger.setup(__name__)

class AuditLoggerSingleton(object):
    """ AuditLoggerSingleton
    
    Used to make AuditLogger a singleton via shared state
    """
    _shared_state = {}
    def __init__(self):
        self.__dict__ = self._shared_state

class AuditLogger(AuditLoggerSingleton):
    """ Audit Logger

        Singleton interface to an audit logging class
    """

    _success = 0
    _failure = 1
    _warning = 2
    _information = 4
    """ The various log levels as defined in init.sql """

    _storage = None
    """ The storage client we should use to talk to the storage service """

    def __init__(self, storage=None):
        AuditLoggerSingleton.__init__(self)
        if self._storage is None:
            if not isinstance(storage, StorageClient):
                raise TypeError('Must be a valid Storage object')
            self._storage = storage

    async def _log(self, level, code, log):
        try:
            if log is None:
                payload = PayloadBuilder().INSERT(code=code, level=level).payload()
            else:
                payload = PayloadBuilder().INSERT(code=code, level=level, log=log).payload()

            # Get the JSON result of the insert
            out_data = self._storage.insert_into_tbl("log", payload)

            # Check if storage output is a dict (JSION data)
            if type(out_data) is dict:
                # Is error message present ?
                err_msg = out_data.get('message', None)

                # Raise a Exception
                if err_msg is not None:
                    raise Exception(str(err_msg))
        except Exception as ex:
            _logger.exception("Failed to log audit trail entry '%s': %s", code, str(ex))
            raise ex

    async def success(self, code, log):
        await self._log(self._success, code, log)

    async def failure(self, code, log):
        await self._log(self._failure, code, log)

    async def warning(self, code, log):
        await self._log(self._warning, code, log)

    async def information(self, code, log):
        await self._log(self._information, code, log)
