'''
A minimal wrapper around shelve to remove the tiniest amount of boilerplate.
'''

import logging
import shelve
from config import DB

def get_value(key):
    '''
    Returns a value from shelve.
    '''
    logging.info(f'key={key}')
    with shelve.open(DB) as shelve_db:
        return shelve_db[key]

def set_value(key, val):
    '''
    Sets a value in shelve.
    '''
    logging.info(f'key={key} val={val}')
    with shelve.open(DB) as shelve_db:
        shelve_db[key] = val
