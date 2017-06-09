'''
All commands and their metadata live in here.
'''

import logging
import os
import sys
import time
from functools import singledispatch
from typing import Callable, Dict, List, NamedTuple, Union

import git

from config import ADMIN, CHANNEL
from slack_utils import (ArgumentType, Channel, EventId, delete_message,
                         get_channel_by_name, get_id, get_reaction_sum,
                         get_user_by_name, post_message, get_users_in_channel, is_active_and_human)
from store import get_value, set_value

ListeningEvent = NamedTuple('ListeningEvent', [
    ('ts', float),
    ('fn', Callable[[], bool])
])

listening: Dict[EventId, ListeningEvent] = {}

SyncCommand = NamedTuple('SyncCommand', [
    ('args', List[ArgumentType]),
    ('fn', Callable),
])

AdminCommand = NamedTuple('AdminCommand', [
    ('args', List[ArgumentType]),
    ('fn', Callable),
])

VoteCommand = NamedTuple('VoteCommand', [
    ('args', List[ArgumentType]),
    ('fn', Callable),
    ('message', Callable),
    ('key', str)
])


@singledispatch
def handler(command: VoteCommand, event, args: List[str], slack_client):
    '''
    Handles vote based commands.
    '''
    logging.info(f'event={event}, args={args}, command={command}')

    # Filter to only the CHANNEL channel.
    voting_channel = get_channel_by_name(slack_client, CHANNEL)
    if event.get('channel', None) != voting_channel:
        return

    channel = event['channel']
    votes_required = get_value(command.key)
    response = post_message(
        slack_client,
        channel,
        f'{command.message(args)()} {votes_required} votes required.'
    )

    def _handler() -> bool:
        reactions = slack_client.api_call(
            'reactions.get',
            channel=response['channel'],
            timestamp=response['ts'],
            full=True
        )
        current_votes = get_reaction_sum(reactions)
        if current_votes >= votes_required:
            command.fn(slack_client, channel, args)
            return True
        else:
            return False

    listening[get_id(response)] = ListeningEvent(time.time(), _handler)


@handler.register(SyncCommand)
def _(command: SyncCommand, event, args: List[str], slack_client):
    '''
    Handlers synchronous commands.
    '''
    logging.info(f'event={event}, args={args}, command={command}')
    command.fn(slack_client, event['channel'], args)


@handler.register(AdminCommand)
def __(command: AdminCommand, event, args: List[str], slack_client):
    '''
    Handles admin level commands.
    '''
    logging.info(f'event={event}, args={args}, command={command}')
    if event['user'] == get_user_by_name(slack_client, ADMIN):
        command.fn(slack_client, event['channel'], args)
    else:
        delete_message(slack_client, event)


def vote_fn(slack_client, channel: Channel, args: List[str]):
    '''
    Changes the number of votes required.
    '''
    command = COMMANDS[args[0]]
    if isinstance(command, VoteCommand):
        set_value(command.key, args[1])
        post_message(slack_client, channel, f'Changed `{args[0]}` to require {args[1]} votes.')


def rename_fn(slack_client, channel: Channel, args: List[str]):
    '''
    Changes the name of a channel.
    '''
    response = slack_client.api_call(
        'channels.rename',
        channel=args[0],
        name=args[1].replace('#', ''),
        validate=True
    )
    if not response['ok']:
        logging.warning(f'could not rename channel response={response}')
        post_message(slack_client, channel,
                     f'Could not rename <#{args[0]}> to {args[1]}.')
    else:
        post_message(slack_client, channel,
                     f'Renamed <#{args[0]}> to {args[1]}.')


def kick_fn(slack_client, channel: Channel, args: List[str]):
    '''
    Kicks a user from a channel.
    '''
    response = slack_client.api_call(
        'channels.kick',
        user=args[0],
        channel=args[1],
    )
    if not response['ok']:
        logging.warning(f'could not kick user response={response}')
        post_message(slack_client, channel,
                     f'Could not kick <@{args[0]}> from <#{args[1]}>.')
    else:
        post_message(slack_client, channel,
                     f'Kicked <@{args[0]}> from <#{args[1]}>.')


def invite_fn(slack_client, channel: Channel, args: List[str]):
    '''
    Invites a user to this slack.
    '''
    response = slack_client.api_call(
        'users.admin.invite',
        email=args[0]
    )
    if not response['ok']:
        logging.warning(f'could not invite user response={response}')
        post_message(slack_client, channel,
                     f'Could not invite <mailto:{args[0]}> to this slack.')
    else:
        post_message(slack_client, channel,
                     f'Invited <mailto:{args[0]}> to this slack.')


def help_fn(slack_client, channel: Channel, args: List[str]):
    '''
    Outputs a help message.
    '''
    help_message = 'Actions are voted on using :+1: and :-1:. I support the following commands:```'
    for key, val in COMMANDS.items():
        line = f"\n– {key}"
        for arg in val.args:
            line += f" <{arg.name}>"
        if isinstance(val, VoteCommand):
            line = line.ljust(35)
            votes_required = get_value(val.key)
            line += f' {votes_required} votes required.'
        help_message += line

    help_message += "```"
    post_message(slack_client, channel, help_message)


def pong_fn(slack_client, channel: Channel, args: List[str]):
    '''
    Outputs a pong.
    '''
    post_message(slack_client, channel, 'pong')


def update_fn(slack_client, channel: Channel, args: List[str]):
    '''
    Pulls from git and reloads the process.
    '''
    g = git.cmd.Git('.')
    try:
        g.pull()
    except:
        post_message(slack_client, channel, f'Could not git pull.')
        return

    # This will not return. Instead, the process will be immediately replaced.
    os.execl(sys.executable, *([sys.executable] + sys.argv))


def intersect_fn(slack_client, channel: Channel, args: List[str]):
    '''
    Gets the intersection of two channels users and pings them.
    '''
    users = get_users_in_channel(slack_client, args[0])
    sresu = get_users_in_channel(slack_client, args[1])

    line = ''
    for user in users.intersection(sresu):
        if is_active_and_human(slack_client, user):
            line += f'<@{user}> '
    if line == '':
        line = 'No intersection.'

    post_message(slack_client, channel, line)

COMMANDS: Dict[str, Union[SyncCommand, VoteCommand, AdminCommand]] = {
    '.help': SyncCommand([], help_fn),
    '.ping': SyncCommand([], pong_fn),
    '.update': AdminCommand([], update_fn),
    '.intersect': SyncCommand([ArgumentType.CHANNEL, ArgumentType.CHANNEL], intersect_fn),
    '.vote': VoteCommand(
        [ArgumentType.COMMAND, ArgumentType.INT],
        vote_fn,
        lambda args: f'Change `{args[0]}` to require {args[1]} votes?',
        'vote'
    ),
    '.rename': VoteCommand(
        [ArgumentType.CHANNEL, ArgumentType.STRING],
        rename_fn,
        lambda args: lambda args: f'Rename <#{args[0]}> to {args[1]}?',
        'rename'
    ),
    '.kick': VoteCommand(
        [ArgumentType.USER, ArgumentType.CHANNEL],
        kick_fn,
        lambda args: f'Kick <@{args[0]}> from <#{args[1]}>?',
        'kick'
    ),
    '.invite': VoteCommand(
        [ArgumentType.EMAIL],
        invite_fn,
        lambda args: lambda args: f'Invite <mailto:{args[0]}> to this slack?',
        'invite'
    ),
}
