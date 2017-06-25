'''
Random utilities that are irrelevant of slack.
'''
import logging
import inspect

def log(fn):
    '''
    Decorator for automatically logging function calls.
    '''
    def logged_fn(*args, **kw):
        '''
        Outputs structured logging for the argument names
        and their values.
        '''
        kargs = {}
        arg_inspection = inspect.getfullargspec(fn).args
        for i in range(0, len(args)):
            kargs[arg_inspection[i]] = args[i]
        kargs.update(kw)
        line = f'[function={fn.__name__}]'
        for key, val in kargs.items():
            line += f'[{key}={val}]'
        logging.info(line)
        result = fn(*args, **kw)
        logging.info(f'[function={fn.__name__}][result={result}]')
        return result
    return logged_fn
