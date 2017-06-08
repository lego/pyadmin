'''
PyAdmin

This is probably not how you should write python, but hey it
looks decent to me.
'''

import logging
import time
from commands import COMMANDS, listening, handler

import schedule
from slackclient import SlackClient

from config import (ADMIN, MAX_LISTENING, SLACK_TOKEN, SLEEP_TIME,
                    configure_logging)
from slack_utils import (delete_message, get_id, get_self, parse_arguments,
                         post_dm)


def prune_listening():
    '''
    Iterates over listening and removes all events which are older
    than MAX_LISTENING seconds.
    '''
    logging.info(f'listening={listening}')
    expired_events = []
    for key, val in listening.items():
        if time.time() - val['ts'] > MAX_LISTENING:
            expired_events.append(key)
    for expired_event in expired_events:
        del listening[expired_event]


def ping_slack():
    '''
    Pings slack through rtm.
    '''
    slack_client.server.ping()


def process_events(events):
    '''
    For each event we filter to reactions and messages
    and route accordingly.
    '''
    if not events:
        return

    for event in events:
        event_type = event.get('type', None)
        if event_type == 'message' and 'text' in event:
            # We only care about top level messages.
            if 'thread_ts' in event:
                break

            # We only care about messages from other users.
            if event['user'] == ME:
                break

            # See if it's a valid command.
            argv = event['text'].split()
            if argv[0] not in COMMANDS:
                # Not a command? Delete!
                delete_message(slack_client, event)
                break

            command = COMMANDS[argv[0]]
            typs, vals = parse_arguments(argv[1:])
            logging.info(f'argv={argv} parse_types={typs} parse_values={vals}')

            if command.args == typs:
                try:
                    handler(command, event, vals, slack_client)
                except Exception:
                    logging.exception('exception encountered running command')
            else:
                # Not a valid command and in CHANNEL? Delete!
                delete_message(slack_client, event)
        elif event_type == 'reaction_added':
            item = event['item']
            if 'channel' in item and 'ts' in item:
                event_id = get_id(event['item'])
                if listening.get(event_id, {'fn': lambda: None})['fn']():
                    del listening[event_id]


if __name__ == '__main__':
    configure_logging()
    schedule.every().hour.do(prune_listening)
    schedule.every().minute.do(ping_slack)
    slack_client = SlackClient(SLACK_TOKEN)
    ME = get_self(slack_client)
    post_dm(slack_client, ADMIN, 'Hello!')

    if slack_client.rtm_connect():
        logging.info('connected')
        while True:
            process_events(slack_client.rtm_read())
            schedule.run_pending()
            time.sleep(SLEEP_TIME)
    else:
        logging.critical('connection failed, invalid token?')
