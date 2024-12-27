import os
from dotenv import load_dotenv
import requests
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, jsonify
from datetime import datetime
import json
from werkzeug.utils import secure_filename
from functools import wraps

# Load environment variables
load_dotenv()

# Settings file path
SETTINGS_FILE = 'settings.json'

def load_settings():
    try:
        with open(SETTINGS_FILE, 'r') as f:
            settings = json.load(f)
            return settings
    except FileNotFoundError:
        print("No settings file found, using defaults")
        return {
            'INSTAGRAM_CLIENT_ID': '1672953986597793',
            'INSTAGRAM_CLIENT_SECRET': '934169c5c167aa3bf82c02b099af5745',
            'INSTAGRAM_REDIRECT_URI': 'http://localhost:5000/auth/instagram/callback'
        }
    except Exception as e:
        print(f"Error loading settings: {e}")
        return {}

def save_settings_to_file(settings):
    print(f"Saving settings to file: {settings}")
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f)
    print("Settings saved successfully")

def get_instagram_settings():
    settings = load_settings()
    print("Debug - Instagram Settings:")
    print(f"Client ID: {settings['INSTAGRAM_CLIENT_ID']}")
    print(f"Redirect URI: {settings['INSTAGRAM_REDIRECT_URI']}")
    return settings

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev_key_123')  # Sicherer Secret Key für Sessions
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False

# File Upload Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create uploads folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scheduler')
def scheduler():
    return render_template('scheduler.html')

@app.route('/schedule_posts', methods=['POST'])
def schedule_posts():
    try:
        captions = request.form.getlist('captions[]')
        schedules = request.form.getlist('schedules[]')
        images = request.files.getlist('images[]')
        
        for caption, schedule, image in zip(captions, schedules, images):
            # Validate and save each post
            if not caption or not schedule or not image:
                flash('Alle Felder müssen ausgefüllt sein', 'error')
                return redirect(url_for('scheduler'))
                
            # Save image and create database entry for each post
            # [Your existing logic for saving posts]
            
        flash(f'{len(captions)} Beiträge wurden erfolgreich geplant', 'success')
        return redirect(url_for('index'))
        
    except Exception as e:
        flash(f'Fehler beim Planen der Beiträge: {str(e)}', 'error')
        return redirect(url_for('scheduler'))

@app.route('/schedule_post', methods=['POST'])
def schedule_post():
    if 'image' not in request.files:
        flash('Kein Bild hochgeladen', 'error')
        return redirect(url_for('scheduler'))

    file = request.files['image']
    if file.filename == '':
        flash('Keine Datei ausgewählt', 'error')
        return redirect(url_for('scheduler'))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        caption = request.form.get('caption', '')
        schedule_time = request.form.get('schedule')

        flash('Beitrag erfolgreich geplant!', 'success')
        return redirect(url_for('scheduler'))

    flash('Ungültiger Dateityp', 'error')
    return redirect(url_for('scheduler'))

@app.route('/auth/instagram')
def instagram_auth():
    settings = get_instagram_settings()
    
    # Basic Display API Berechtigungen
    scopes = 'basic'  # Grundlegende Berechtigung für Basic Display API
    
    # Instagram OAuth URL für Basic Display API
    auth_url = 'https://api.instagram.com/oauth/authorize'
    params = {
        'client_id': settings['INSTAGRAM_CLIENT_ID'],
        'redirect_uri': settings['INSTAGRAM_REDIRECT_URI'],
        'scope': scopes,
        'response_type': 'code',
        'state': 'instagram_auth'  # Sicherheitstoken
    }
    
    # Erstelle die vollständige Auth URL
    full_auth_url = f"{auth_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
    print(f"Auth URL: {full_auth_url}")  # Debug-Ausgabe
    return redirect(full_auth_url)

@app.route('/auth/instagram/callback')
def instagram_callback():
    try:
        code = request.args.get('code')
        if not code:
            flash('Fehlender Autorisierungscode', 'error')
            return redirect(url_for('index'))

        settings = get_instagram_settings()
        print(f"Received code: {code}")  # Debug-Ausgabe
        
        # Token von Instagram Basic Display API erhalten
        token_url = 'https://api.instagram.com/oauth/access_token'
        token_data = {
            'client_id': settings['INSTAGRAM_CLIENT_ID'],
            'client_secret': settings['INSTAGRAM_CLIENT_SECRET'],
            'grant_type': 'authorization_code',
            'redirect_uri': settings['INSTAGRAM_REDIRECT_URI'],
            'code': code
        }
        
        print(f"Token request data: {token_data}")  # Debug-Ausgabe
        token_response = requests.post(token_url, data=token_data)
        print(f"Token response: {token_response.text}")  # Debug-Ausgabe
        token_response.raise_for_status()
        
        # Access Token und User ID extrahieren
        token_data = token_response.json()
        access_token = token_data.get('access_token')
        user_id = token_data.get('user_id')
        
        if not access_token or not user_id:
            raise Exception("Kein Access Token oder User ID erhalten")
        
        # Token in Session speichern
        session['instagram_access_token'] = access_token
        session['instagram_user_id'] = user_id
        
        flash('Erfolgreich mit Instagram verbunden!', 'success')
        return redirect(url_for('dashboard'))

    except Exception as e:
        print(f"Error in callback: {str(e)}")
        flash(f'Fehler bei der Authentifizierung: {str(e)}', 'error')
        return redirect(url_for('index'))

def generate_appsecret_proof(access_token):
    import hmac
    import hashlib
    import time
    
    app_secret = os.getenv('FACEBOOK_APP_SECRET')
    timestamp = int(time.time())
    hmac_object = hmac.new(
        app_secret.encode('utf-8'),
        msg=f'{access_token}|{timestamp}'.encode('utf-8'),
        digestmod=hashlib.sha256
    )
    return hmac_object.hexdigest(), timestamp

@app.route('/auth/facebook/callback')
def facebook_callback():
    access_token = request.args.get('access_token')
    if not access_token:
        flash('Fehler bei der Authentifizierung', 'error')
        return redirect(url_for('index'))
    
    # Generate appsecret_proof
    appsecret_proof, timestamp = generate_appsecret_proof(access_token)
    
    # Get user info with appsecret_proof
    params = {
        'access_token': access_token,
        'appsecret_proof': appsecret_proof,
        'appsecret_time': timestamp,
        'fields': 'id,name,accounts{instagram_business_account}'
    }
    
    response = requests.get('https://graph.facebook.com/v18.0/me', params=params)
    if response.status_code != 200:
        flash('Fehler beim Abrufen der Benutzerinformationen', 'error')
        return redirect(url_for('index'))

    user_data = response.json()
    session['user_id'] = user_data.get('id')
    session['access_token'] = access_token
    
    # Get Instagram business account
    accounts_data = user_data.get('accounts', {}).get('data', [])
    for account in accounts_data:
        if account.get('instagram_business_account'):
            session['instagram_business_account_id'] = account['instagram_business_account']['id']
            break
    
    return render_template('facebook_callback.html')

@app.route('/dashboard')
def dashboard():
    if 'page_access_token' not in session or 'instagram_account_id' not in session:
        flash('Bitte melden Sie sich zuerst an', 'error')
        return redirect(url_for('index'))
    
    try:
        # Instagram Business Account Informationen abrufen
        account_url = f"https://graph.facebook.com/v18.0/{session['instagram_account_id']}"
        params = {
            'fields': 'username,profile_picture_url,media_count,media{caption,media_url,thumbnail_url,permalink,media_type,timestamp}',
            'access_token': session['page_access_token']
        }
        
        response = requests.get(account_url, params=params)
        response.raise_for_status()
        account_info = response.json()
        
        # Media-Daten extrahieren
        media = account_info.get('media', {}).get('data', [])
        
        return render_template('dashboard.html', 
                             user_info={
                                 'username': account_info.get('username'),
                                 'profile_picture_url': account_info.get('profile_picture_url'),
                                 'media_count': account_info.get('media_count')
                             },
                             media=media)
        
    except Exception as e:
        flash(f'Fehler beim Laden der Account-Informationen: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/login')
def facebook_login():
    return render_template('facebook_login.html')

@app.route('/data-deletion')
def data_deletion():
    return render_template('data_deletion.html')

@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/deauthorize', methods=['POST'])
def deauthorize():
    try:
        # Verarbeite die Deauthorisierung von Instagram
        signed_request = request.form.get('signed_request')
        if not signed_request:
            return jsonify({'error': 'No signed_request parameter'}), 400

        # Hier können Sie den signed_request verarbeiten und die Benutzerinformationen löschen
        # Für jetzt senden wir einfach eine erfolgreiche Antwort
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/data-deletion', methods=['POST'])
def data_deletion_post():
    try:
        # Verarbeite die Datenlöschungsanfrage von Instagram
        signed_request = request.form.get('signed_request')
        if not signed_request:
            return jsonify({'error': 'No signed_request parameter'}), 400

        # Hier können Sie den signed_request verarbeiten und die Benutzerdaten löschen
        # Für jetzt senden wir einfach eine erfolgreiche Antwort
        return jsonify({
            'url': 'https://instaapp.onrender.com/privacy-policy',
            'confirmation_code': 'CONFIRMATION_CODE'
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)