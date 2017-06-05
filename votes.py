'''
Small helper script to quickly show, set, delete etc from our db.
'''

import sys
import shelve
from config import DB

args = sys.argv[1:]
command = args[0]

if command == "list":
    with shelve.open(DB) as db:
        for k, v in db.items():
            print(f'{k}: {v}')
elif command == "set":
    key = args[1]
    val = args[2]

    with shelve.open(DB) as db:
        db[key] = int(val)
elif command == "delete":
    key = args[1]
    with shelve.open(DB) as db:
        del db[key]
else:
    print('invalid command')
