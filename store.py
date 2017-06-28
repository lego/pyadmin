'''
A minimal wrapper around shelve to remove the tiniest amount of boilerplate.
'''

import shelve

from config import DB
from util import log

class DiskStore:
    '''
    Disk store is a basic store which persists to disk.
    '''
    @staticmethod
    @log
    def get_value(key):
        '''
        Returns a value from shelve.
        '''
        with shelve.open(DB) as shelve_db:
            if key not in shelve_db:
                shelve_db[key] = 1
            return shelve_db[key]


    @staticmethod
    @log
    def set_value(key, val):
        '''
        Sets a value in shelve.
        '''
        with shelve.open(DB) as shelve_db:
            shelve_db[key] = val
