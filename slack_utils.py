'''
Various slack utilities, mostly related to parsing arguments.
'''

import commands
import logging
import re
from enum import Enum, auto
from functools import lru_cache
from typing import Any, Dict, List, NewType, Tuple, Set

from config import CHANNEL

Channel = NewType('Channel', str)
User = NewType('User', str)
EventId = NewType('EventId', str)


class ApiCallException(Exception):
    '''
    Used when slack_client.api_call(...) fails.
    '''
    pass


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


def parse_channel(input_string: str) -> Tuple[Any, bool]:
    '''
    Input format: <#C052EM50K|waterloo>
    '''
    match = re.search('<#(?P<id>[^|]+)|(?P<name>[^>])>', input_string)
    if not match:
        return None, False
    return (ArgumentType.CHANNEL, match.group('id')), True


def parse_user(input_string: str) -> Tuple[Any, bool]:
    '''
    Input format: <@U088EGWEL>
    '''
    match = re.search('<@(?P<id>[^>]+)>', input_string)
    if not match:
        return None, False
    return (ArgumentType.USER, match.group('id')), True


def parse_email(input_string: str) -> Tuple[Any, bool]:
    '''
    Input format: <mailto:tsohlson@gmail.com|tsohlson@gmail.com>
    '''
    match = re.search('<mailto:(?P<email>[^|]+).+>', input_string)
    if not match:
        return None, False
    return (ArgumentType.EMAIL, match.group('email')), True


def parse_command(input_string: str) -> Tuple[Any, bool]:
    '''
    Input format: $rename. Only accepts commands which are votable.
    '''
    if input_string in commands.COMMANDS:
        if 'key' in commands.COMMANDS[input_string]:
            return (ArgumentType.COMMAND, input_string), True
    return None, False


def parse_int(input_string: str) -> Tuple[Any, bool]:
    '''
    Input format: 5
    '''
    try:
        return (ArgumentType.INT, int(input_string)), True
    except ValueError:
        return None, False


def parse_arguments(args: List[str]) -> Tuple[List[ArgumentType], List[str]]:
    '''
    Given a list of strings we parse each one and output two lists.
    The first list contains the types e.g. string, channel, user, email
    The second list contains the values e.g. pickle, C052EM50K, U088EGWEL, tsohlson@gmail.com
    '''
    logging.info(f'args={args}')
    typs: List[ArgumentType] = []
    vals: List[str] = []
    for arg in args:
        # The string type is the most lenient so we default to that.
        typ: ArgumentType = ArgumentType.STRING
        val: str = arg
        for parse in [parse_channel, parse_user, parse_email, parse_command, parse_int]:
            res, match = parse(arg)
            if match:
                typ = res[0]
                val = res[1]
        typs.append(typ)
        vals.append(val)
    return typs, vals


def get_id(event: Dict) -> EventId:
    '''
    Returns the ID for an event given an event with a ts key and a
    channel key.
    '''
    return event['channel'] + event['ts']


def get_reaction_sum(event: Dict) -> int:
    '''
    Returns the number of thumbs up - the number of thumbs down given
    an event with a message key which has a reaction key.
    '''
    logging.info(f'event={event}')
    up_votes: int = 0
    down_votes: int = 0
    for reaction in event['message']['reactions']:
        if reaction['name'] == '+1':
            up_votes += reaction['count']
        if reaction['name'] == '-1':
            down_votes += reaction['count']
    return up_votes - down_votes


def post_message(slack_client, channel: Channel, text: str) -> Dict:
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
        raise ApiCallException(response)
    return response


def post_dm(slack_client, user_name: str, text: str) -> Dict:
    '''
    Takes a user name (e.g. tristan) and sends them a message.
    '''
    usr = get_user_by_name(slack_client, user_name)
    response = slack_client.api_call('im.open', user=usr)
    if not response['ok']:
        raise ApiCallException(response)

    return post_message(slack_client, response['channel']['id'], text)


@lru_cache()
def get_channel_by_name(slack_client, channel_name: str) -> Channel:
    '''
    Returns the channel ID from the name.
    '''
    response = slack_client.api_call('channels.list')
    if not response['ok']:
        raise ApiCallException(response)
    for ch in response['channels']:
        if ch['name'] == channel_name:
            return ch['id']

    raise ApiCallException(response)


@lru_cache()
def get_user_by_name(slack_client, user_name: str) -> User:
    '''
    Returns the user ID from name.
    '''
    response = slack_client.api_call('users.list', presence=False)
    if not response['ok']:
        raise ApiCallException(response)
    for usr in response['members']:
        if usr['name'] == user_name:
            return usr['id']

    raise ApiCallException(response)


@lru_cache()
def get_users_in_channel(slack_client, channel: Channel) -> Set[User]:
    '''
    Returns a list of the users in a channel.
    '''
    response = slack_client.api_call('channels.', channel=channel)
    if not response['ok']:
        raise ApiCallException(response)

    return set(response.get('channel', {}).get('members', []))


@lru_cache()
def is_bot(slack_client, user: User) -> bool:
    '''
    Takes a user ID and returns true if the user is a bot.
    '''
    if user == 'USLACKBOT':
        return True

    response = slack_client.api_call('users.info', user=user)
    if not response['ok']:
        # We don't raise an exception here since the caller of
        # this method does not handle exceptions.
        logging.warning(f'response={response}')
        return False

    return response.get('user', {}).get('is_bot', False)


def get_self(slack_client) -> User:
    '''
    Uses auth.test to get the current user id.
    '''
    response = slack_client.api_call('auth.test')
    if not response['ok']:
        raise ApiCallException(response)

    return response['user_id']


def delete_message(slack_client, event):
    '''
    Given a message event we attempt to delete it.
    '''
    # We only delete messages from one channel.
    channel = event['channel']
    if channel != get_channel_by_name(slack_client, CHANNEL):
        return

    response = slack_client.api_call(
        'chat.delete',
        ts=event['ts'],
        channel=channel
    )
    if not response['ok']:
        logging.warning(f'response={response}')
