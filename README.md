## Setup
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
I use a simple `config.py` file to handle configuration. There's a sample one, though you'll need to change the token to something valid.