## Setup
Something along the lines of...
```
git clone git@github.com:tristan-ohlson/pyadmin.git
cd pyadmin
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
mkdir logs
python main.py
```

## Config
I use a simple `config.py` file to handle configuration. Currently it looks like:
```
import logging
from datetime import datetime

def configure_logging():
    '''
    Sets up logging formatting and output file.
    '''
    logging.basicConfig(filename=f'logs/{datetime.now()}.log', level=logging.DEBUG, format=FORMAT)

CHANNEL_NAME = 'admin'
FORMAT = "[%(asctime)s] [%(levelname)-8s] [%(funcName)-16s] [%(message)s]"
DB = 'db'
SLEEP_TIME = 0.1
SLACK_TOKEN = [token]
MAX_LISTENING = 86400 # 24 hours in seconds
```