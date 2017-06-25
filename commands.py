'''
All commands and their metadata live in here.
'''

import os
import sys
import time
from functools import singledispatch
from operator import eq
from typing import Dict, List

import git

from config import ADMIN, CHANNEL
from parser import Argument, ArgumentMatcher, ArgumentType
from slack import get_id
from store import get_value, set_value
from util import log


class ListeningEvent:
    def __init__(self, ts, fn):
        self.ts = ts
        self.fn = fn


class Command:
    '''
    Base class for all command types.
    '''

    def __init__(self, name: str, args: List[ArgumentMatcher], fn, cmp=eq) -> None:
        self.name = name
        self.args = args
        self.fn = fn
        self.cmp = cmp
        self.args.insert(0, ArgumentMatcher(ArgumentType.COMMAND, name))

    def matches(self, args: List[Argument]):
        '''
        Returns true if the arguments matches this command.
        '''
        return self.cmp(self.args, args)

    def __repr__(self):
        return f'Command({self.name}, {self.args})'

    def __str__(self):
        return f'Command({self.name}, {self.args})'


class SyncCommand(Command):
    '''
    A sync command will execute synchronously.
    '''
    pass


class AdminCommand(Command):
    '''
    An admin command is runnable only by admins.
    '''
    pass


class VoteCommand(Command):
    '''
    A vote command will start a vote and wait for enough
    votes before running.
    '''

    def __init__(self, name: str, args: List[ArgumentMatcher], fn, message, key) -> None:
        super(VoteCommand, self).__init__(name, args, fn)
        self.message = message
        self.key = key


listening: Dict[str, ListeningEvent] = {}


def loose_cmp(matchers: List[ArgumentMatcher], arguments: List[Argument]):
    '''
    Returns true if one of the lists extends the other.
    e.g. loose_cmp([1, 2], [1, 2, 3]) returns true.
    '''
    length = len(matchers)
    return matchers[:length] == arguments[:length]


@singledispatch
@log
def handler(command: Command, event, args: List[Argument], slack_client):
    '''
    Function is only here for single dispatch.
    '''
    raise Exception('should never be called')


@handler.register(VoteCommand)
@log
def _vote_handler(command: VoteCommand, event, args: List[Argument], slack_client):
    '''
    Handles vote based commands.
    '''
    # Filter to only the CHANNEL channel.
    voting_channel = slack_client.get_channel_by_name(CHANNEL)
    channel = event['channel']
    if channel != voting_channel:
        return

    votes_required = get_value(command.key)
    response = slack_client.send_message(
        channel, f'{command.message(args)} {votes_required} votes required.')

    def _handler():
        current_votes = slack_client.get_reaction_sum(response)
        if current_votes >= votes_required:
            command.fn(slack_client, channel, args)
            return True
        else:
            return False

    listening[get_id(response)] = ListeningEvent(time.time(), _handler)


@handler.register(SyncCommand)
@log
def _sync_handler(command: SyncCommand, event, args: List[Argument], slack_client):
    '''
    Handlers synchronous commands.
    '''
    command.fn(slack_client, event['channel'], args)


@handler.register(AdminCommand)
@log
def _admin_handler(command: AdminCommand, event, args: List[Argument], slack_client):
    '''
    Handles admin level commands.
    '''
    if event['user'] == slack_client.get_user_by_name(ADMIN):
        command.fn(slack_client, event['channel'], args)
    else:
        slack_client.delete_message(event)


def vote_fn(slack_client, channel, args: List[Argument]):
    '''
    Changes the number of votes required.
    '''
    command_name = args[1].val
    new_value = args[2].val

    command = next(cmd for cmd in COMMANDS if cmd.name == command_name)
    set_value(command.key, new_value)
    slack_client.send_message(
        channel, f'Changed `{command_name}` to require {new_value} votes.')


def rename_fn(slack_client, channel, args: List[Argument]):
    '''
    Changes the name of a channel.
    '''
    channel_id = args[1].val
    new_name = args[2].val
    original_name = slack_client.get_channel_name(channel_id)

    response = slack_client.rename_channel(channel_id, new_name)
    if not response['ok']:
        slack_client.send_message(
            channel, f'Could not rename <#{channel_id}> to {new_name}.')
    else:
        slack_client.send_message(
            channel, f'Renamed <#{channel_id}> from #{original_name} to {new_name}.')


def kick_fn(slack_client, channel, args: List[Argument]):
    '''
    Kicks a user from a channel.
    '''
    user = args[1].val
    chan = args[2].val
    response = slack_client.kick_user(user, chan)
    if not response['ok']:
        slack_client.send_message(
            channel, f'Could not kick <@{user}> from <#{chan}>.')
    else:
        slack_client.send_message(
            channel, f'Kicked <@{user}> from <#{chan}>.')


def invite_fn(slack_client, channel, args: List[Argument]):
    '''
    Invites a user to this slack.
    '''
    email = args[1].val
    response = slack_client.invite_email(email)
    if not response['ok']:
        slack_client.send_message(
            channel, f'Could not invite <mailto:{email}> to this slack.')
    else:
        slack_client.send_message(
            channel, f'Invited <mailto:{email}> to this slack.')


def help_fn(slack_client, channel, args: List[Argument]):
    '''
    Outputs a help message.
    '''
    help_message = 'Actions are voted on using :+1: and :-1:. I support the following commands:```'
    for cmd in COMMANDS:
        line = f"\n– {cmd.name}"
        for arg in cmd.args:
            if arg.typ != ArgumentType.COMMAND:
                line += f" <{arg.typ}>"
        if isinstance(cmd, VoteCommand):
            line = line.ljust(35)
            votes_required = get_value(cmd.key)
            line += f' {votes_required} votes required.'
        help_message += line

    help_message += "```"
    slack_client.send_message(channel, help_message)


def pong_fn(slack_client, channel, args: List[Argument]):
    '''
    Outputs a pong.
    '''
    slack_client.send_message(channel, 'pong')


def ping_fn(slack_client, channel, args: List[Argument]):
    '''
    Outputs a ping.
    '''
    slack_client.send_message(channel, 'ping')


def update_fn(slack_client, channel, args: List[Argument]):
    '''
    Pulls from git and reloads the process.
    '''
    g = git.cmd.Git('.')
    try:
        g.pull()
    except:
        slack_client.send_message(channel, f'Could not git pull.')
        return

    # This will not return. Instead, the process will be immediately replaced.
    os.execl(sys.executable, *([sys.executable] + sys.argv))


def _intersect(slack_client, channel, lennahc) -> str:
    '''
    Returns a formatted string of users in channel and lennahc.
    '''
    users = slack_client.get_users_in_channel(channel)
    sresu = slack_client.get_users_in_channel(lennahc)

    line = ''
    for user in users.intersection(sresu):
        if slack_client.is_active_and_human(user):
            line += f'<@{user}> '
    if line == '':
        line = 'No intersection.'
    return line


def intersect_fn(slack_client, channel, args: List[Argument]):
    '''
    Gets the intersection of two channels users and pings them.
    '''
    intersection = _intersect(slack_client, args[1].val, args[2].val)
    slack_client.send_message(channel, intersection)


def intersect_short_fn(slack_client, channel, args: List[Argument]):
    '''
    Intersect but shortcuts to using current channel as one half of
    the intersection.
    '''
    intersection = _intersect(slack_client, args[1].val, channel)
    slack_client.send_message(channel, intersection)


ANY_CHANNEL = ArgumentMatcher(ArgumentType.CHANNEL)
ANY_VOTE_COMMAND = ArgumentMatcher(ArgumentType.VOTING_COMMAND)
ANY_INT = ArgumentMatcher(ArgumentType.INT)
ANY_STRING = ArgumentMatcher(ArgumentType.STRING)
ANY_USER = ArgumentMatcher(ArgumentType.USER)
ANY_EMAIL = ArgumentMatcher(ArgumentType.EMAIL)

COMMANDS: List[Command] = [
    SyncCommand('.help', [], help_fn),
    SyncCommand('.ping', [], pong_fn),
    SyncCommand('.pong', [], ping_fn),
    SyncCommand(
        '.intersect',
        [ANY_CHANNEL, ANY_CHANNEL],
        intersect_fn,
        cmp=loose_cmp
    ),
    SyncCommand(
        '.intersect',
        [ANY_CHANNEL],
        intersect_short_fn,
        cmp=loose_cmp
    ),
    AdminCommand('.update', [], update_fn),
    VoteCommand(
        '.vote',
        [ANY_VOTE_COMMAND, ANY_INT],
        vote_fn,
        lambda args: f'Change `{args[0]}` to require {args[1]} votes?',
        'vote'
    ),
    VoteCommand(
        '.rename',
        [ANY_CHANNEL, ANY_STRING],
        vote_fn,
        lambda args: f'Rename <#{args[0]}> to {args[1]}?',
        'rename'
    ),
    VoteCommand(
        '.kick',
        [ANY_USER, ANY_CHANNEL],
        kick_fn,
        lambda args: f'Kick <@{args[0]}> from <#{args[1]}>?',
        'kick'
    ),
    VoteCommand(
        '.invite',
        [ANY_EMAIL],
        invite_fn,
        lambda args: f'Invite <mailto:{args[0]}> to this slack?',
        'invite'
    ),
]
