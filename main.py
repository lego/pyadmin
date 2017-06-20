'''
PyAdmin

This is probably not how you should write python, but hey it
looks decent to me.
'''

import logging
import time
from commands import COMMANDS, handler, listening

import schedule
from slackclient import SlackClient

from config import (MAX_LISTENING, SLACK_TOKEN, SLEEP_TIME, UPDATE_CHANNEL,
                    configure_logging)
from slack_utils import (ApiCallException, EventId, User, delete_message,
                         get_channel_by_name, get_id, get_self,
                         get_user_by_name, get_users_in_channel, is_bot,
                         parse_arguments, post_message)


def prune_listening():
    '''
    Iterates over listening and removes all events which are older
    than MAX_LISTENING seconds.
    '''
    logging.info(f'listening={listening}')
    expired_events = []
    for key, val in listening.items():
        if time.time() - val.ts > MAX_LISTENING:
            expired_events.append(key)
    for expired_event in expired_events:
        del listening[expired_event]


def ping_slack():
    '''
    Pings slack through rtm.
    '''
    slack_client.server.ping()


def expire_cache():
    '''
    Expires cached slack information.
    '''
    get_channel_by_name.cache_clear()
    get_user_by_name.cache_clear()
    get_users_in_channel.cache_clear()


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

            # Sometimes this isn't here apparently.
            if 'user' not in event:
                break

            # We only care about messages from other users.
            if event['user'] == ME:
                break

            # Ignore bot users.
            if is_bot(slack_client, event['user']):
                delete_message(slack_client, event)
                break

            # See if it's a valid command.
            argv = event['text'].split()

            # Sometimes there's nothing here. Unsure what's up with that.
            if argv.empty():
                delete_message(slack_client, event)
                break

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
                except ApiCallException as api_call_exception:
                    logging.warning(api_call_exception)
            else:
                # Not a valid command and in CHANNEL? Delete!
                delete_message(slack_client, event)
        elif event_type == 'reaction_added':
            item = event['item']
            if 'channel' in item and 'ts' in item:
                event_id: EventId = get_id(event['item'])
                if event_id in listening:
                    if listening[event_id].fn():
                        del listening[event_id]


def run():
    '''
    Main event loop.
    '''
    if slack_client.rtm_connect():
        logging.info('connected')
        while True:
            process_events(slack_client.rtm_read())
            schedule.run_pending()
            time.sleep(SLEEP_TIME)
    else:
        raise Exception('connection failed')


if __name__ == '__main__':
    configure_logging()

    schedule.every().hour.do(prune_listening)
    schedule.every().minute.do(ping_slack)
    schedule.every().hour.do(expire_cache)

    slack_client = SlackClient(SLACK_TOKEN)

    ME: User = get_self(slack_client)

    while True:
        try:
            post_message(slack_client, UPDATE_CHANNEL, 'Started.')
            run()
        except:
            post_message(slack_client, UPDATE_CHANNEL, 'Unhandled exception.')
            logging.exception('unhandled exception')
            time.sleep(20)
