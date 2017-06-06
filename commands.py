'''
All commands and their metadata live in here.
'''

import logging
import time
from store import get_value, set_value
from slack_utils import ArgumentType, get_id, get_reaction_sum, post_message

listening = {}

def handler_handler(slack_client, event, args, command):
    '''
    The master function. Does some master stuff.
    '''
    logging.info(f'event={event}, args={args}, command={command}')

    channel = event['channel']
    if command['vote']:
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
                command['handler'](slack_client, channel, args)
                return True
            else:
                return False

        listening[get_id(response)] = {'ts': time.time(), 'fn': handler}
    else:
        post_message(slack_client, channel, command['message'](args))

def vote_handler(slack_client, channel, args):
    '''
    Changes the number of votes required.
    '''
    set_value(COMMANDS[args[0]]['key'], args[1])
    post_message(slack_client, channel, f'Changed `{args[0]}` to require {args[1]} votes.')

def rename_handler(slack_client, channel, args):
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

def kick_handler(slack_client, channel, args):
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

def invite_handler(slack_client, channel, args):
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

HELP_MESSAGE = '''Actions are voted on using :+1: and :-1:. I support the following commands:
    – `$help`
    – `$vote <command> <int>`
    – `$rename <channel> <string>`
    – `$kick <user> <channel>`
    – `$invite <email>`'''

COMMANDS = {
    '$help': {
        'args': [],
        'message': lambda args: HELP_MESSAGE,
        'vote': False,
    },
    '$vote': {
        'args': [ArgumentType.COMMAND, ArgumentType.INT],
        'handler': vote_handler,
        'message': lambda args: f'Change `{args[0]}` to require {args[1]} votes?',
        'vote': True,
        'key': 'vote'
    },
    '$rename': {
        'args': [ArgumentType.CHANNEL, ArgumentType.STRING],
        'handler': rename_handler,
        'message': lambda args: f'Rename <#{args[0]}> to {args[1]}?',
        'vote': True,
        'key': 'rename'
    },
    '$kick': {
        'args': [ArgumentType.USER, ArgumentType.CHANNEL],
        'handler': kick_handler,
        'message': lambda args: f'Kick <@{args[0]}> from <#{args[1]}>?',
        'vote': True,
        'key': 'kick'
    },
    '$invite':{
        'args': [ArgumentType.EMAIL],
        'handler': invite_handler,
        'message': lambda args: f'Invite <mailto:{args[0]}> to this slack?',
        'vote': True,
        'key': 'invite'
    }
}
