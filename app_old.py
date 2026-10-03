# app.py - Updated with fixes for user display and logout
import sys
import importlib.util

# === PYTHON 3.14 COMPATIBILITY FIXES ===
if sys.version_info >= (3, 14):
    import pkgutil
    
    # Fix 1: pkgutil.get_loader
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
    
    # Fix 2: werkzeug.urls.url_decode
    try:
        import werkzeug.urls
        if not hasattr(werkzeug.urls, 'url_decode'):
            werkzeug.urls.url_decode = werkzeug.urls.url_unquote_plus
    except:
        pass

# === IMPORTS ===
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from authlib.integrations.flask_client import OAuth
import math
from config import Config
import socket
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

# === APP INITIALIZATION ===
app = Flask(__name__)
app.config.from_object(Config)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Initialize OAuth
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=app.config['GOOGLE_CLIENT_ID'],
    client_secret=app.config['GOOGLE_CLIENT_SECRET'],
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id, email, name):
        self.id = id
        self.email = email
        self.name = name

@login_manager.user_loader
def load_user(user_id):
    # In a real app, you'd load from a database
    # For now, we'll create a user with the ID
    return User(user_id, None, None)

# === ROUTES ===
@app.route('/')
@login_required
def index():
    # Get the user's name from the session if available
    user_name = session.get('user_name', current_user.name or 'User')
    return render_template('index.html', 
                         com_usd=app.config['COM_USD'] * 100,
                         com_bol=app.config['COM_BOL'] * 100,
                         com_fija=app.config['COM_FIJA'],
                         com_var=app.config['COM_VAR'] * 100,
                         user_name=user_name)

@app.route('/login')
def login():
    redirect_uri = url_for('authorize', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/authorize')
def authorize():
    try:
        token = google.authorize_access_token()
        
        # Try to get userinfo from the token
        user_info = token.get('userinfo')
        if user_info is None:
            # If not in token, fetch from Google API
            resp = google.get('https://www.googleapis.com/oauth2/v1/userinfo', token=token)
            user_info = resp.json()
        
        # Extract user information
        user_id = user_info.get('id')
        user_email = user_info.get('email')
        user_name = user_info.get('name', user_email.split('@')[0])  # Use email username if name not available
        
        # Store user name in session
        session['user_name'] = user_name
        
        # Create user object
        user = User(user_id, user_email, user_name)
        login_user(user)
        
        return redirect(url_for('index'))
    except Exception as e:
        print(f"Authorization error: {e}")
        return f"Authorization failed: {str(e)}", 400

@app.route('/logout')
@login_required
def logout():
    # Clear session data
    session.clear()
    # Logout the user
    logout_user()
    # Redirect to login page
    return redirect(url_for('login'))

@app.route('/calculate', methods=['POST'])
@login_required
def calculate():
    try:
        data = request.get_json()
        
        currency = data.get('currency')
        monto = float(data.get('monto', 0))
        tipo_cambio_usd_cad = float(data.get('tipo_cambio_usd_cad', 0))
        tipo_cambio_usd_bol = float(data.get('tipo_cambio_usd_bol', 0))
        
        if monto <= 0:
            return jsonify({'success': False, 'error': 'MONTO must be greater than 0'}), 400
        if tipo_cambio_usd_cad <= 0:
            return jsonify({'success': False, 'error': 'USD/CAD rate must be greater than 0'}), 400
        if tipo_cambio_usd_bol <= 0:
            return jsonify({'success': False, 'error': 'USD/BOL rate must be greater than 0'}), 400
        
        com_bol = app.config['COM_BOL']
        com_fija = app.config['COM_FIJA']
        com_var = app.config['COM_VAR']
        com_usd = app.config['COM_USD']
        
        # Verificando el monto enviado es mayor a 500 USD 
        monto_usd = monto / tipo_cambio_usd_bol if currency == 'BOL' else monto
        print(monto_usd)
        
        if monto_usd <= 500:
            comision = com_fija
            rate_applied = 'COM_FIJA'
        else:
            comision = com_var * monto_usd
            rate_applied = 'COM_VAR'
        
        if currency == 'BOL':
            result = ((monto_usd + comision) * (1+com_bol)) / tipo_cambio_usd_cad
            
        else:
            result = ((monto_usd + comision) * (1+com_usd)) / tipo_cambio_usd_cad
            
        result_rounded = math.ceil(result)
        
        return jsonify({
            'success': True,
            'result': result_rounded,
            'details': {
                'commission': round(comision, 2),
                'rate_applied': rate_applied
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

if __name__ == '__main__':
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    
    print(f"\n{'='*60}")
    print(f"Transferencia a Bolivia Portal is running!")
    print(f"Local access: http://localhost:8081")
    print(f"Network access: http://{local_ip}:8081")
    print(f"{'='*60}\n")
    
    app.run(host='0.0.0.0', port=8081, debug=True)