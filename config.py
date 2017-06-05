'''
Various configurations and methods around them.
'''

import logging
from datetime import datetime

def configure_logging():
    '''
    Sets up logging formatting and output file.
    '''
    logging.basicConfig(filename=f'logs/{datetime.now()}.log', level=logging.DEBUG, format=FORMAT)

CHANNEL_NAME = 'admin'
FORMAT = "[%(asctime)s] [%(levelname)-8s] [%(funcName)-16s] [%(message)s]"
DB = 'db.db'
SLEEP_TIME = 0.1
SLACK_TOKEN = 'xoxp-5060173286-8286574496-179397985905-fe55d1bf97ee718ab46f5b26b2f2e426'
