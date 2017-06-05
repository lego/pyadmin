'''
Various slack utilities, mostly related to parsing arguments.
'''

import re
import logging
import commands
from enum import Enum, auto

class ArgumentType(Enum):
    '''
    ArgumentType is an enum of all the different types
    of arguments from slack.
    '''
    CHANNEL = auto()
    USER = auto()
    EMAIL = auto()
    STRING = auto()
    COMMAND = auto()
    INT = auto()

def parse_channel(input_string):
    '''
    Input format: <#C052EM50K|waterloo>
    '''
    logging.info(f'input_string={input_string}')
    match = re.search('<#(?P<id>[^|]+)|(?P<name>[^>])>', input_string)
    if not match:
        return None, False
    return (ArgumentType.CHANNEL, match.group('id')), True

def parse_user(input_string):
    '''
    Input format: <@U088EGWEL>
    '''
    logging.info(f'input_string={input_string}')
    match = re.search('<@(?P<id>[^>]+)>', input_string)
    if not match:
        return None, False
    return (ArgumentType.USER, match.group('id')), True

def parse_email(input_string):
    '''
    Input format: <mailto:tsohlson@gmail.com|tsohlson@gmail.com>
    '''
    logging.info(f'input_string={input_string}')
    match = re.search('<mailto:(?P<email>[^|]+).+>', input_string)
    if not match:
        return None, False
    return (ArgumentType.EMAIL, match.group('email')), True

def parse_command(input_string):
    '''
    Input format: $rename
    '''
    logging.info(f'input_string={input_string}')
    if input_string in commands.COMMANDS:
        return (ArgumentType.COMMAND, input_string), True
    return None, False

def parse_int(input_string):
    '''
    Input format: 5
    '''
    logging.info(f'input_string={input_string}')
    try:
        return (ArgumentType.INT, int(input_string)), True
    except ValueError:
        return None, False

def parse_arguments(args):
    '''
    Given a list of strings we parse each one and output two lists.
    The first list contains the types e.g. string, channel, user, email
    The second list contains the values e.g. pickle, C052EM50K, U088EGWEL, tsohlson@gmail.com
    '''
    logging.info(f'args={args}')
    typs = []
    vals = []
    for arg in args:
        # The string type is the most lenient so we default to that.
        typ = ArgumentType.STRING
        val = arg
        for parse in [parse_channel, parse_user, parse_email, parse_command, parse_int]:
            res, match = parse(arg)
            if match:
                typ = res[0]
                val = res[1]
        typs.append(typ)
        vals.append(val)
    return typs, vals

def get_id(event):
    '''
    Returns the ID for an event given an event with a ts key and a
    channel key.
    '''
    logging.info(f'event={event}')
    return event['channel'] + event['ts']

def get_reaction_sum(event):
    '''
    Returns the number of thumbs up - the number of thumbs down given
    an event with a message key which has a reaction key.
    '''
    logging.info(f'event={event}')
    up_votes = 0
    down_votes = 0
    for reaction in event['message']['reactions']:
        if reaction['name'] == '+1':
            up_votes += 1
        if reaction['name'] == '-1':
            down_votes += 1
    return up_votes - down_votes

def post_message(slack_client, channel, text):
    '''
    Simple wrapper around slack_client.api_call('chat.postMessage'...).
    '''
    response = slack_client.api_call(
        'chat.postMessage',
        channel=channel,
        text=text,
        as_user=True
    )
    if not response['ok']:
        logging.error(f'response={response}')
        raise Exception('could not post message')
    return response

def get_channel_by_name(slack_client, channel):
    '''
    Returns the channel ID from the name or None.
    '''
    response = slack_client.api_call(
        'channels.list'
    )
    if not response['ok']:
        raise Exception('could not get channel')
    for ch in response['channels']:
        if ch['name'] == channel:
            return ch['id']

    raise Exception(f'could not find channel response={response}')

def get_self(slack_client):
    '''
    Uses auth.test to get the current user id.
    '''
    response = slack_client.api_call(
        'auth.test'
    )
    if not response['ok']:
        raise Exception(f'could not get self response={response}')

    return response['user_id']

def delete_message(slack_client, event):
    '''
    Given a message event we attempt to delete it.
    '''
    response = slack_client.api_call(
        'chat.delete',
        ts=event['ts'],
        channel=event['channel']
    )
    if not response['ok']:
        logging.warning(f'response={response}')
