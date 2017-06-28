'''
Various slack utilities, mostly related to parsing arguments.
'''
import re
from enum import Enum, auto
from typing import List, Tuple

from util import log


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
    VOTING_COMMAND = auto()

    def __str__(self):
        return self.name


class Argument:
    '''
    An argument has a type and a value.
    '''

    def __init__(self, typ: ArgumentType, val) -> None:
        self.typ = typ
        self.val = val

    def __eq__(self, other):
        if isinstance(other, Argument):
            return self.typ == other.typ and self.val == other.val
        elif isinstance(other, ArgumentMatcher):
            # Defer to the ArgumentMatcher's __eq__ override.
            return other == self

    def __str__(self):
        return f'{self.val}'

    def __repr__(self):
        return f'Argument({self.typ}, {self.val})'


class ArgumentMatcher:
    '''
    An argument matcher is similar to an Argument, however the value
    can be None to signify "any" or a value. It allows us to have:
    Argument(Channel, '#CU019203') be equal to ArgumentMatcher(Channel)
    '''

    def __init__(self, typ: ArgumentType, desired=None) -> None:
        self.typ = typ
        self.desired = desired

    def __eq__(self, other):
        if isinstance(other, ArgumentMatcher):
            return self.typ == other.typ and self.desired == other.desired
        if isinstance(other, Argument):
            if self.desired is None:
                return self.typ == other.typ
            else:
                return self.typ == other.typ and self.desired == other.val

    def __str__(self):
        if self.desired != None:
            return f'{self.desired}'
        else:
            return f'<{self.typ}>'

    def __repr__(self):
        return self.__str__()


def parse_channel(input_string: str) -> Tuple[Argument, bool]:
    '''
    Input format: <#C052EM50K|waterloo>
    '''
    match = re.search('<#(?P<id>[^|]+)|(?P<name>[^>])>', input_string)
    if not match:
        return None, False
    return Argument(ArgumentType.CHANNEL, match.group('id')), True


def parse_user(input_string: str) -> Tuple[Argument, bool]:
    '''
    Input format: <@U088EGWEL>
    '''
    match = re.search('<@(?P<id>[^>]+)>', input_string)
    if not match:
        return None, False
    return Argument(ArgumentType.USER, match.group('id')), True


def parse_email(input_string: str) -> Tuple[Argument, bool]:
    '''
    Input format: <mailto:tsohlson@gmail.com|tsohlson@gmail.com>
    '''
    match = re.search('<mailto:(?P<email>[^|]+).+>', input_string)
    if not match:
        return None, False
    return Argument(ArgumentType.EMAIL, match.group('email')), True


def parse_command(input_string: str) -> Tuple[Argument, bool]:
    '''
    Input format: $rename. Only accepts commands which are votable.
    '''
    import commands
    for command in commands.COMMANDS:
        if command.name == input_string and not isinstance(command, commands.VoteCommand):
            return Argument(ArgumentType.COMMAND, input_string), True
    return None, False


def parse_voting_command(input_string: str) -> Tuple[Argument, bool]:
    '''
    Input format: $rename. Only accepts commands which are votable.
    '''
    import commands
    for command in commands.COMMANDS:
        if command.name == input_string and isinstance(command, commands.VoteCommand):
            return Argument(ArgumentType.VOTING_COMMAND, input_string), True
    return None, False


def parse_int(input_string: str) -> Tuple[Argument, bool]:
    '''
    Input format: 5
    '''
    try:
        return Argument(ArgumentType.INT, int(input_string)), True
    except ValueError:
        return None, False


@log
def parse_arguments(args: List[str]) -> List[Argument]:
    '''
    Given a list of strings we parse each one and output two lists.
    The first list contains the types e.g. string, channel, user, email
    The second list contains the values e.g. pickle, C052EM50K, U088EGWEL, tsohlson@gmail.com
    '''
    parsed_args: List[Argument] = []
    for arg in args:
        # The string type is the most lenient so we default to that.
        default = Argument(ArgumentType.STRING, arg)
        for parse in [parse_channel, parse_user, parse_email, parse_command,
                      parse_voting_command, parse_int]:
            res, match = parse(arg)
            if match:
                default = res
        parsed_args.append(default)
    return parsed_args
