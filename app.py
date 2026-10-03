# app.py - Production-ready version with Basic Auth, rate limiting, and logging
import sys
import importlib.util
import requests               

# === PYTHON 3.14 COMPATIBILITY FIXES ===
if sys.version_info >= (3, 14):
    import pkgutil
    if not hasattr(pkgutil, 'get_loader'):
        def get_loader(module_name):
            try:
                spec = importlib.util.find_spec(module_name)
                if spec is not None:
                    return spec.loader
            except (ImportError, AttributeError):
                pass
            return None
        pkgutil.get_loader = get_loader

# === IMPORTS ===
from flask import Flask, render_template, request, jsonify, Response
from flask_httpauth import HTTPBasicAuth
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
import math
import os
import logging
import time
from logging.handlers import RotatingFileHandler
from datetime import datetime
from collections import defaultdict
from config import Config
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

# === APP INITIALIZATION ===
app = Flask(__name__)
app.config.from_object(Config)

# === LOGGING SETUP ===
def setup_logging(app):
    """Configure application logging with rotation and multiple handlers."""
    log_dir = app.config['LOG_DIR']
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_level = getattr(logging, app.config['LOG_LEVEL'].upper(), logging.INFO)
    formatter = logging.Formatter(
        app.config['LOG_FORMAT'],
        datefmt=app.config['LOG_DATE_FORMAT']
    )

    # All app logs
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'portal.log'),
        maxBytes=app.config['LOG_MAX_BYTES'],
        backupCount=app.config['LOG_BACKUP_COUNT'],
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    # Errors only
    error_handler = RotatingFileHandler(
        os.path.join(log_dir, 'errors.log'),
        maxBytes=app.config['LOG_MAX_BYTES'],
        backupCount=app.config['LOG_BACKUP_COUNT'],
        encoding='utf-8'
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)

    # Console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)

    app.logger.handlers.clear()
    app.logger.addHandler(file_handler)
    app.logger.addHandler(error_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(log_level)

    # Transaction logger
    transaction_logger = logging.getLogger('transactions')
    transaction_logger.handlers.clear()
    txn_handler = RotatingFileHandler(
        os.path.join(log_dir, 'transactions.log'),
        maxBytes=app.config['LOG_MAX_BYTES'],
        backupCount=app.config['LOG_BACKUP_COUNT'],
        encoding='utf-8'
    )
    txn_handler.setFormatter(formatter)
    transaction_logger.addHandler(txn_handler)
    transaction_logger.addHandler(file_handler)
    transaction_logger.setLevel(logging.INFO)
    transaction_logger.propagate = False

    # Access logger
    access_logger = logging.getLogger('access')
    access_logger.handlers.clear()
    access_handler = RotatingFileHandler(
        os.path.join(log_dir, 'access.log'),
        maxBytes=app.config['LOG_MAX_BYTES'],
        backupCount=app.config['LOG_BACKUP_COUNT'],
        encoding='utf-8'
    )
    access_handler.setFormatter(formatter)
    access_logger.addHandler(access_handler)
    access_logger.setLevel(logging.INFO)
    access_logger.propagate = False

    # Auth logger (login attempts)
    auth_logger = logging.getLogger('auth')
    auth_logger.handlers.clear()
    auth_handler = RotatingFileHandler(
        os.path.join(log_dir, 'auth.log'),
        maxBytes=app.config['LOG_MAX_BYTES'],
        backupCount=app.config['LOG_BACKUP_COUNT'],
        encoding='utf-8'
    )
    auth_handler.setFormatter(formatter)
    auth_logger.addHandler(auth_handler)
    auth_logger.addHandler(file_handler)
    auth_logger.setLevel(logging.INFO)
    auth_logger.propagate = False

    app.logger.info("=" * 60)
    app.logger.info("Logging initialized")
    app.logger.info(f"Log directory: {log_dir}")
    app.logger.info(f"Log level: {app.config['LOG_LEVEL']}")
    app.logger.info("=" * 60)
    return app.logger

logger = setup_logging(app)
transaction_logger = logging.getLogger('transactions')
access_logger = logging.getLogger('access')
auth_logger = logging.getLogger('auth')

# === SECURITY: BASIC AUTH ===
auth = HTTPBasicAuth()
auth.realm = "Transferencia a Bolivia"

USERS = {
    app.config['PORTAL_USER']: generate_password_hash(app.config['PORTAL_PASS'])
}

# In-memory failed login tracker: { ip: [timestamps] }
failed_attempts = defaultdict(list)
FAILED_WINDOW_SECONDS = 300   # 5 minutes
FAILED_THRESHOLD = 10          # 10 failures in 5 min = warn

def get_client_ip():
    """Return the real client IP, honoring proxy headers."""
    return (
        request.headers.get('CF-Connecting-IP') or
        request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or
        request.remote_addr
    )

@auth.verify_password
def verify_password(username, password):
    ip = get_client_ip()
    ua = request.headers.get('User-Agent', 'Unknown')[:120]

    if username in USERS and check_password_hash(USERS[username], password):
        auth_logger.info(f"AUTH OK | user={username} | ip={ip} | ua={ua}")
        return username

    # Track failures
    now = time.time()
    failed_attempts[ip] = [t for t in failed_attempts[ip] if now - t < FAILED_WINDOW_SECONDS]
    failed_attempts[ip].append(now)

    auth_logger.warning(
        f"AUTH FAIL | user={username} | ip={ip} | ua={ua} | "
        f"failures_in_window={len(failed_attempts[ip])}"
    )
    if len(failed_attempts[ip]) >= FAILED_THRESHOLD:
        auth_logger.error(
            f"BRUTE FORCE SUSPECTED | ip={ip} | "
            f"{len(failed_attempts[ip])} failures in {FAILED_WINDOW_SECONDS}s"
        )
    return None

@auth.error_handler
def auth_error():
    return Response(
        "Authentication required.\n", 401,
        {'WWW-Authenticate': f'Basic realm="{auth.realm}"'}
    )

# === RATE LIMITING ===
limiter = Limiter(
    key_func=get_client_ip,
    app=app,
    default_limits=[app.config['RATE_DEFAULT']],
    storage_uri="memory://",
)

# === SECURITY HEADERS ===
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Cache-Control'] = 'no-store'
    return response

# === REQUEST LOGGING ===
@app.before_request
def log_request():
    ip = get_client_ip()
    ua = request.headers.get('User-Agent', 'Unknown')[:100]
    access_logger.info(f"REQUEST | {request.method} {request.path} | ip={ip} | ua={ua}")

@app.after_request
def log_response(response):
    access_logger.info(f"RESPONSE | {request.method} {request.path} | status={response.status_code}")
    return response

def get_usd_bol_rate():
    """Fetch the official USD/BOL exchange rate from the API.
    Returns a tuple: (rate_value, rate_date) or (None, None) on failure.
    """
    url = "https://apibcb.cucu.bo/api/v1/tc/oficial"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()

        tc = data.get('tc_oficial', {})
        rate = tc.get('valor')
        fecha = tc.get('fecha', '')

        if rate is None:
            logger.warning("API response missing 'tc_oficial.valor'")
            return None, None

        logger.info(f"Fetched USD/BOL rate: {rate} ({fecha})")
        return rate, fecha

    except requests.exceptions.RequestException as e:
        logger.warning(f"Could not fetch USD/BOL rate: {e}")
        return None, None
    except ValueError as e:
        logger.warning(f"Invalid JSON from rate API: {e}")
        return None, None

# === ROUTES ===
@app.route('/')
@auth.login_required
@limiter.limit("60 per minute")
def index():
    usd_bol_rate, usd_bol_date = get_usd_bol_rate()                                               
    return render_template(
        'index.html',
        com_usd=app.config['COM_USD'] * 100,
        com_bol=app.config['COM_BOL'] * 100,
        com_fija=app.config['COM_FIJA'],
        com_var=app.config['COM_VAR'] * 100,
        usd_bol_rate=usd_bol_rate,
        usd_bol_date=usd_bol_date,                          
    )

@app.route('/calculate', methods=['POST'])
@auth.login_required
@limiter.limit(app.config['RATE_CALCULATE'])
def calculate():
    start_time = datetime.now()
    ip = get_client_ip()
    try:
        data = request.get_json(silent=True) or {}
        currency = data.get('currency')
        monto = float(data.get('monto', 0))
        tipo_cambio_usd_cad = float(data.get('tipo_cambio_usd_cad', 0))
        tipo_cambio_usd_bol = float(data.get('tipo_cambio_usd_bol', 0))

        if currency not in ('USD', 'BOL'):
            return jsonify({'success': False, 'error': 'Invalid currency'}), 400
        if monto <= 0:
            return jsonify({'success': False, 'error': 'MONTO must be > 0'}), 400
        if tipo_cambio_usd_cad <= 0:
            return jsonify({'success': False, 'error': 'USD/CAD must be > 0'}), 400
        if tipo_cambio_usd_bol <= 0:
            return jsonify({'success': False, 'error': 'USD/BOL must be > 0'}), 400

        com_bol = app.config['COM_BOL']
        com_fija = app.config['COM_FIJA']
        com_var = app.config['COM_VAR']
        com_usd = app.config['COM_USD']

        monto_usd = monto / tipo_cambio_usd_bol if currency == 'BOL' else monto

        if monto_usd <= 500:
            comision = com_fija
            rate_applied = 'COM_FIJA'
        else:
            comision = com_var * monto_usd
            rate_applied = 'COM_VAR'

        if currency == 'BOL':
            result = ((monto_usd + comision) * (1 + com_bol)) / tipo_cambio_usd_cad
        else:
            result = ((monto_usd + comision) * (1 + com_usd)) / tipo_cambio_usd_cad

        result_rounded = math.ceil(result)
        elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000

        transaction_logger.info(
            f"TXN | ip={ip} | cur={currency} | monto={monto} | "
            f"usd_cad={tipo_cambio_usd_cad} | usd_bol={tipo_cambio_usd_bol} | "
            f"monto_usd={round(monto_usd, 2)} | comm={round(comision, 2)} ({rate_applied}) | "
            f"result={result_rounded} CAD | {elapsed_ms:.1f}ms"
        )

        return jsonify({
            'success': True,
            'result': result_rounded,
            'details': {
                'commission': round(comision, 2),
                'rate_applied': rate_applied,
                'monto_usd': round(monto_usd, 2)
            }
        })

    except ValueError:
        logger.warning(f"Invalid numeric input from ip={ip}")
        return jsonify({'success': False, 'error': 'Invalid number format'}), 400
    except Exception as e:
        logger.exception(f"Unexpected error from ip={ip}: {e}")
        return jsonify({'success': False, 'error': 'Unexpected error'}), 500

# === ERROR HANDLERS ===
@app.errorhandler(404)
def not_found(error):
    logger.warning(f"404 | path={request.path} | ip={get_client_ip()}")
    return jsonify({'success': False, 'error': 'Not found'}), 404

@app.errorhandler(429)
def rate_limited(error):
    logger.warning(f"RATE LIMIT | ip={get_client_ip()} | path={request.path}")
    return jsonify({'success': False, 'error': 'Too many requests'}), 429

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500 | path={request.path} | ip={get_client_ip()}")
    return jsonify({'success': False, 'error': 'Internal server error'}), 500

# === DEV ENTRY POINT ===
if __name__ == '__main__':
    logger.info("Starting in DEVELOPMENT mode (do not expose to internet)")
    app.run(host='0.0.0.0', port=8081, debug=False)