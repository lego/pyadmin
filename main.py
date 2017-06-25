'''
PyAdmin

This is probably not how you should write python, but hey it
looks decent to me.
'''

import logging
import time
from commands import COMMANDS, handler, listening

import schedule

from config import (MAX_LISTENING, SLACK_TOKEN, SLEEP_TIME, UPDATE_CHANNEL,
                    configure_logging)

from parser import parse_arguments
from slack import ApiCallException, Client, get_id

def prune_listening():
    '''
    Iterates over listening and removes all events which are older
    than MAX_LISTENING seconds.
    '''
    expired_events = []
    for key, val in listening.items():
        if time.time() - val.ts > MAX_LISTENING:
            expired_events.append(key)
    for expired_event in expired_events:
        del listening[expired_event]


def process_event(event):
    '''
    For each event we filter to reactions and messages
    and route accordingly.
    '''

    event_type = event.get('type', None)
    if event_type == 'message' and 'text' in event:
        # We only care about top level messages.
        if 'thread_ts' in event:
            return

        # Sometimes this isn't here apparently.
        if 'user' not in event:
            return

        # We only care about messages from other users.
        if event['user'] == slack_client.self:
            return

        # Ignore bot users.
        if slack_client.is_bot(event['user']):
            slack_client.delete_message(event)
            return

        argv = event['text'].split()
        parsed_args = parse_arguments(argv)
        for command in COMMANDS:
            if command.matches(parsed_args):
                handler(command, event, parsed_args, slack_client)
                return

        # Probably not a valid command
        slack_client.delete_message(event)
    elif event_type == 'reaction_added':
        item = event['item']
        if 'channel' in item and 'ts' in item:
            event_id = get_id(event['item'])
            if event_id in listening:
                if listening[event_id].fn():
                    del listening[event_id]

def run():
    '''
    Main event loop.
    '''
    if slack_client.rtm_connect():
        while True:
            events = slack_client.rtm_read()
            for event in events:
                try:
                    process_event(event)
                except ApiCallException as api_call_exception:
                    logging.warning(api_call_exception)
            schedule.run_pending()
            time.sleep(SLEEP_TIME)
    else:
        raise ConnectionError()


if __name__ == '__main__':
    configure_logging()

    slack_client = Client(SLACK_TOKEN)

    schedule.every().hour.do(prune_listening)

    # Not sure if this is useful yet. Might assure that we
    # reconnect to slack if we ever DC.
    schedule.every().minute.do(slack_client.ping)

    while True:
        try:
            slack_client.send_message(UPDATE_CHANNEL, 'Started.')
            run()
        except ConnectionError:
            logging.warning('could not connect to slack')
            time.sleep(10)
        except KeyboardInterrupt:
            break
        except:
            slack_client.send_message(UPDATE_CHANNEL, 'Unhandled exception.')
            logging.exception('unhandled exception')
            time.sleep(10)
