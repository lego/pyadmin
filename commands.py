'''
All commands and their metadata live in here.
'''

import logging
import time
import sys
import os
import git
from config import ADMIN, CHANNEL
from store import get_value, set_value
from slack_utils import (ArgumentType, get_id, get_reaction_sum, post_message,
                         get_channel_by_name, get_user_by_name)

listening = {}

def vote_handler(slack_client, event, args, command):
    '''
    Handles vote based commands.
    '''
    logging.info(f'event={event}, args={args}, command={command}')

    # Filter to only the CHANNEL channel.
    channel_id = get_channel_by_name(slack_client, CHANNEL)
    if event.get('channel', None) != channel_id:
        return

    channel = event['channel']
    votes_required = get_value(command['key'])
    response = post_message(
        slack_client,
        channel,
        command['message'](args) + f' {votes_required} votes required.'
    )

    def handler():
        reactions = slack_client.api_call(
            'reactions.get',
            channel=response['channel'],
            timestamp=response['ts'],
            full=True
        )
        current_votes = get_reaction_sum(reactions)
        if current_votes >= votes_required:
            command['fn'](slack_client, channel, args)
            return True
        else:
            return False

    listening[get_id(response)] = {'ts': time.time(), 'fn': handler}

def synchronous_handler(slack_client, event, args, command):
    '''
    Handlers synchronous commands.
    '''
    logging.info(f'event={event}, args={args}, command={command}')
    command['fn'](slack_client, event['channel'], args)

def admin_handler(slack_client, event, args, command):
    '''
    Handles admin level commands.
    '''
    logging.info(f'event={event}, args={args}, command={command}')
    if event['user'] == get_user_by_name(slack_client, ADMIN):
        command['fn'](slack_client, event['channel'], args)

def vote_fn(slack_client, channel, args):
    '''
    Changes the number of votes required.
    '''
    set_value(COMMANDS[args[0]]['key'], args[1])
    post_message(slack_client, channel, f'Changed `{args[0]}` to require {args[1]} votes.')

def rename_fn(slack_client, channel, args):
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
        post_message(slack_client, channel, f'Could not rename <#{args[0]}> to {args[1]}.')
    else:
        post_message(slack_client, channel, f'Renamed <#{args[0]}> to {args[1]}.')

def kick_fn(slack_client, channel, args):
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
        post_message(slack_client, channel, f'Could not kick <@{args[0]}> from <#{args[1]}>.')
    else:
        post_message(slack_client, channel, f'Kicked <@{args[0]}> from <#{args[1]}>.')

def invite_fn(slack_client, channel, args):
    '''
    Invites a user to this slack.
    '''
    response = slack_client.api_call(
        'users.admin.invite',
        email=args[0]
    )
    if not response['ok']:
        logging.warning(f'could not invite user response={response}')
        post_message(slack_client, channel, f'Could not invite <mailto:{args[0]}> to this slack.')
    else:
        post_message(slack_client, channel, f'Invited <mailto:{args[0]}> to this slack.')

def help_fn(slack_client, channel, args):
    '''
    Outputs a help message.
    '''
    help_message = '''Actions are voted on using :+1: and :-1:. I support the following commands:
    – `$help`
    – `$vote <command> <int>`
    – `$rename <channel> <string>`
    – `$kick <user> <channel>`
    – `$invite <email>`'''

    post_message(slack_client, channel, help_message)

def pong_fn(slack_client, channel, args):
    '''
    Outputs a pong.
    '''
    post_message(slack_client, channel, 'pong')

def update_fn(slack_client, channel, args):
    '''
    Pulls from git and reloads the process.
    '''
    g = git.cmd.Git('.')
    try:
        g.pull()
    except Exception:
        post_message(slack_client, channel, f'Could not git pull.')
        return

    # This will not return. Instead, the process will be immediately replaced.
    os.execl(sys.executable, *([sys.executable]+sys.argv))

COMMANDS = {
    '$update': {
        'args': [],
        'handler': admin_handler,
        'fn': update_fn
    },
    '$help': {
        'args': [],
        'handler': synchronous_handler,
        'fn': help_fn
    },
    '$ping': {
        'args': [],
        'handler': synchronous_handler,
        'fn': pong_fn
    },
    '$vote': {
        'args': [ArgumentType.COMMAND, ArgumentType.INT],
        'handler': vote_handler,
        'fn': vote_fn,
        'message': lambda args: f'Change `{args[0]}` to require {args[1]} votes?',
        'key': 'vote'
    },
    '$rename': {
        'args': [ArgumentType.CHANNEL, ArgumentType.STRING],
        'handler': vote_handler,
        'fn': rename_fn,
        'message': lambda args: f'Rename <#{args[0]}> to {args[1]}?',
        'key': 'rename'
    },
    '$kick': {
        'args': [ArgumentType.USER, ArgumentType.CHANNEL],
        'handler': vote_handler,
        'fn': kick_fn,
        'message': lambda args: f'Kick <@{args[0]}> from <#{args[1]}>?',
        'key': 'kick'
    },
    '$invite': {
        'args': [ArgumentType.EMAIL],
        'handler': vote_handler,
        'fn': invite_fn,
        'message': lambda args: f'Invite <mailto:{args[0]}> to this slack?',
        'key': 'invite'
    },
}
