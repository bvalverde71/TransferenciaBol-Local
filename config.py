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
    print(PORTAL_USER)

    # === RATE LIMITING ===
    RATE_DEFAULT = os.environ.get('RATE_DEFAULT', '200 per hour')
    RATE_CALCULATE = os.environ.get('RATE_CALCULATE', '30 per minute')
    RATE_LOGIN_FAIL = os.environ.get('RATE_LOGIN_FAIL', '10 per minute')

    # === LOGGING ===
    LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_MAX_BYTES = 5 * 1024 * 1024   # 5 MB
    LOG_BACKUP_COUNT = 5
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'