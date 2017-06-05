## Setup
```
git clone git@github.com:tristan-ohlson/pyadmin.git
cd pyadmin
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Config
I use a simple `config.py` file to handle configuration. Right now it looks like this:
```
import logging
from datetime import datetime

def configure_logging():
    logging.basicConfig(filename=f'logs/{datetime.now()}.log', level=logging.DEBUG, format=FORMAT)

FORMAT = "[%(asctime)s] [%(levelname)-8s] [%(funcName)-16s] [%(message)s]"
DB = 'db.db'
SLEEP_TIME = 0.1
SLACK_TOKEN = [token]
```