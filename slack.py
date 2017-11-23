'''
Wrapper around slack client so that we can test easily.
'''

from functools import lru_cache
from slackclient import SlackClient
from selenium import webdriver

import config

# driver is used for accessing Admin options that are not exposed via.
# an API, such as updating the workspace name.
driver = webdriver.PhantomJS()
# TBH, not sure if this is required.
driver.set_window_size(1024, 768)


class ApiCallException(Exception):
    '''
    Used for when an API call fails.
    '''
    pass


class Client(SlackClient):
    '''
    Wrapper around SlackClient.
    '''

    def __init__(self, token):
        super(Client, self).__init__(token)
        self.admin_channel = self.get_channel_by_name(config.CHANNEL)
        response = self.api_call('auth.test')
        if not response['ok']:
            raise Exception('could not get self')
        self.self = response['user_id']

    def send_message(self, channel, text):
        '''
        Posts text to the given channel.
        '''
        response = check(self.api_call(
            'chat.postMessage',
            channel=channel,
            text=text,
            as_user=True
        ))
        return response

    def send_dm(self, user_name, text):
        '''
        Takes a user_name (not ID) and sends them a DM.
        '''
        user = self.get_user_by_name(user_name)
        response = check(self.api_call('im.open', user=user))
        return self.send_message(response['channel']['id'], text)

    def get_user_by_name(self, user_name):
        '''
        Returns user_name's ID.
        '''
        response = check(self.api_call('users.list', presence=False))
        for user in response['members']:
            if user['name'] == user_name:
                return user['id']

        raise ApiCallException(response)

    def get_users_in_channel(self, channel):
        '''
        Returns a set of users in a channel.
        '''
        response = check(self.api_call('channels.info', channel=channel))
        return set(response['channel']['members'])

    def get_channel_by_name(self, channel_name):
        '''
        Returns channel_name's channel ID.
        '''
        response = check(self.api_call('channels.list'))
        for channel in response['channels']:
            if channel['name'] == channel_name:
                return channel['id']

        raise ApiCallException(response)

    def get_channel_name(self, channel):
        '''
        Returns the name for the given channel.
        '''
        response = check(self.api_call('channels.info', channel=channel))
        return response['channel']['name']

    def rename_channel(self, channel, name):
        '''
        Renames a channel. We don't check response in this function.
        '''
        return self.api_call(
            'channels.rename',
            channel=channel,
            name=name.replace('#', ''),
            validate=True
        )

    def kick_user(self, user, channel):
        '''
        Kicks a user from a channel. We don't check response in this function.
        '''
        return self.api_call(
            'channels.kick',
            user=user,
            channel=channel
        )

    def invite_email(self, email):
        '''
        Invites a user to this slack. We don't check response in this function.
        '''
        return self.api_call(
            'users.admin.invite',
            email=email
        )

    def get_reaction_sum(self, event):
        '''
        Returns the number of thumbs up - the number of thumbs down for
        a given event.
        '''
        reactions = check(self.api_call(
            'reactions.get',
            channel=event['channel'],
            timestamp=event['ts'],
            full=True
        ))
        return get_reaction_sum(reactions)

    def delete_message(self, event):
        '''
        Given an event we attempt to delete it.
        '''
        channel = event['channel']
        if channel != self.admin_channel:
            return

        check(self.api_call('chat.delete', ts=event['ts'], channel=channel))

    @lru_cache()
    def is_bot(self, user):
        '''
        Returns true if the user is a bot.
        '''
        if user == 'USLACKBOT':
            return True

        response = check(self.api_call('users.info', user=user))
        return response['user']['is_bot']

    @lru_cache()
    def is_active_and_human(self, user):
        '''
        Returns true if the user is active and human.
        '''
        response = check(self.api_call('users.info', user=user))
        user_info = response['user']
        return not user_info['deleted'] and not user_info['is_bot']

    def ping(self):
        '''
        Sends a ping to slack.
        '''
        self.server.ping()

    def update_team_name(self):
        '''
        Updates a team name on Slack. It uses a phantomJS browser to do
        this through the Slack Admin website.
        '''

        new_workspace_name = "lalala"
        # FIXME(joey): Badmin login details. Ideally this comes from
        # environment variables.
        SLACK_TEAM = "some_slack_team"
        BADMIN_LOGIN = "some@email.com"
        BADMIN_PASSWORD = "xxxx"

        # Delete all cookies to remove the past login session. This
        # ensures that we log in as expected every time.
        # TODO(joey): We can instead detect whether we need to log in
        # again (i.e. a redirect).
        driver.delete_all_cookies()
        # Open the slack admin page.
        driver.get(
            'https://{slackTeam}.slack.com/admin/name'.format(slackTeam=SLACK_TEAM))

        login_form_email = driver.find_element_by_id('email')
        login_form_password = driver.find_element_by_id('password')
        login_form_submit = driver.find_element_by_id('signin_btn')

        # Enter the email into the form. Sadly, this workaround is
        # required because sending keys to the email field does nothing.
        # An educated guess is that phantomJS does not interact
        # correctly with HTML5 validated fields, in paritcular, HTML5
        # email validation.
        driver.execute_script(
            "document.getElementById('{}').value='{}'".format("email", BADMIN_LOGIN))

        # Fill in the password field.
        login_form_password.clear()
        login_form_password.send_keys(BADMIN_PASSWORD)

        # Submit the login form.
        login_form_submit.click()

        # We have now navigated to the Workspace Name and URL setting page.
        workspace_form_team_name = driver.find_element_by_id('team_name_input')
        workspace_form_submit = driver.find_element_by_id('submit_btn')

        workspace_form_team_name.clear()
        workspace_form_team_name.send_keys(new_workspace_name)

        # Submit the new workspace page.
        workspace_form_submit.click()

        # TODO(joey): Detect if we have encountered an error.

def get_id(event):
    '''
    Returns the ID for an event given an event with a ts key and a
    channel key.
    '''
    return event['channel'] + event['ts']


def check(response):
    '''
    Throws exception if response is not okay.
    '''
    if not response['ok']:
        raise ApiCallException(response)
    return response


def get_reaction_sum(event):
    '''
    Returns the number of thumbs up - the number of thumbs down given
    an event with a message key which has a reaction key.
    '''
    count = 0
    for reaction in event['message']['reactions']:
        if reaction['name'] == '+1':
            count += reaction['count']
        elif reaction['name'] == '-1':
            count -= reaction['count']
    return count
