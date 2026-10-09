# config.py
import os
from dotenv import load_dotenv

class Config:
    # === CORE === # This not used
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'change-this-in-production'

    # === INTERNAL CALCULATION PARAMETERS ===
    COM_USD = 0.03   # 3%
    COM_BOL = 0.025   # 2%
    COM_FIJA = 10
    COM_VAR = 0.02   # 2%

    # === BASIC AUTH ===
    load_dotenv()
    PORTAL_USER = os.getenv("ADM_USER")
    PORTAL_PASS = os.getenv("ADM_PASS")
    #print(PORTAL_USER)

    # === USERS ===
    # Add or remove users here. Passwords must be hashed.
    # To generate a hash, run in Python:
    #   from werkzeug.security import generate_password_hash
    #   print(generate_password_hash('your_password'))
    USERS = {
        'boris': 'scrypt:32768:8:1$UIcvMtzvPUavLofr$71725047614e11c20c5c4bf4f61f869368766ea13ed897c2e790c368b658c359aa72397f55bf836478a8100fd4fd2606e3d6aa5be5d62411738ad262f5486779',
    }


    # === RATE LIMITING ===
    RATE_DEFAULT = os.environ.get('RATE_DEFAULT', '200 per hour')
    RATE_CALCULATE = os.environ.get('RATE_CALCULATE', '30 per minute')
    RATE_LOGIN = os.environ.get('RATE_LOGIN', '10 per minute')

    # === LOGGING ===
    LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_MAX_BYTES = 5 * 1024 * 1024   # 5 MB
    LOG_BACKUP_COUNT = 5
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'