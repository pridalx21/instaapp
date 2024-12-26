import os
from dotenv import load_dotenv
import requests
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
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

@app.route('/auth/facebook/callback')
def facebook_callback():
    try:
        access_token = request.args.get('access_token')
        if not access_token:
            flash('Kein Access Token erhalten', 'error')
            return redirect(url_for('index'))

        # Token in Session speichern
        session['access_token'] = access_token

        # Instagram Business Account ID abrufen
        accounts_url = 'https://graph.facebook.com/v18.0/me/accounts'
        accounts_response = requests.get(accounts_url, params={'access_token': access_token})
        accounts_response.raise_for_status()
        
        accounts_data = accounts_response.json().get('data', [])
        if not accounts_data:
            flash('Keine Facebook Seiten gefunden. Bitte erstellen Sie zuerst eine Facebook Seite.', 'error')
            return redirect(url_for('index'))

        # Erste Facebook Seite verwenden
        page = accounts_data[0]
        page_access_token = page['access_token']
        page_id = page['id']

        # Instagram Business Account ID abrufen
        instagram_account_url = f'https://graph.facebook.com/v18.0/{page_id}?fields=instagram_business_account&access_token={page_access_token}'
        instagram_response = requests.get(instagram_account_url)
        instagram_response.raise_for_status()
        
        instagram_data = instagram_response.json()
        if 'instagram_business_account' not in instagram_data:
            flash('Kein Instagram Business Account gefunden. Bitte verbinden Sie zuerst Ihre Facebook Seite mit einem Instagram Business Account.', 'error')
            return redirect(url_for('index'))

        instagram_account_id = instagram_data['instagram_business_account']['id']
        
        # Tokens und IDs in Session speichern
        session['page_access_token'] = page_access_token
        session['instagram_account_id'] = instagram_account_id
        
        flash('Erfolgreich mit Instagram verbunden!', 'success')
        return redirect(url_for('dashboard'))

    except Exception as e:
        flash(f'Fehler bei der Authentifizierung: {str(e)}', 'error')
        return redirect(url_for('index'))

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

if __name__ == '__main__':
    app.run(debug=True)