'''
All commands and their metadata live in here.
'''

import logging
from store import get_value, set_value
from slack_utils import ArgumentType, get_id, get_reaction_sum, post_message

listening = {}

def handler_handler(slack_client, event, args, command):
    '''
    The master function. Does some master stuff.
    '''
    logging.info(f'event={event}, args={args}, command={command}')

    channel = event['channel']
    response = post_message(slack_client, channel, command['message'](args))

    if command['vote']:
        votes_required = get_value(command['key'])

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

        listening[get_id(response)] = handler

def vote_handler(slack_client, channel, args):
    '''
    Changes the number of votes required.
    '''
    set_value(COMMANDS[args[0]]['key'], args[1])
    post_message(slack_client, channel, 'Value set.')

def rename_handler(slack_client, channel, args):
    '''
    Changes the name of a channel.
    '''
    response = slack_client.api_call(
        'channels.rename',
        channel=args[0],
        name=args[1],
        validate=True
    )
    if not response['ok']:
        logging.warning(f'could not rename channel response={response}')
        post_message(slack_client, channel, 'Could not rename channel.')
    else:
        post_message(slack_client, channel, 'Channel renamed.')

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
        post_message(slack_client, channel, 'Could not kick user.')
    else:
        post_message(slack_client, channel, 'User kicked.')

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
        post_message(slack_client, channel, 'Could not invite user.')
    else:
        post_message(slack_client, channel, 'Invited user')

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
