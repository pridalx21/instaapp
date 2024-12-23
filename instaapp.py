import os
from dotenv import load_dotenv
import requests
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from datetime import datetime
import json
from werkzeug.utils import secure_filename

# Load environment variables
load_dotenv()

# Settings file path
SETTINGS_FILE = 'settings.json'

def load_settings():
    try:
        with open(SETTINGS_FILE, 'r') as f:
            settings = json.load(f)
            print(f"Loaded settings from file: {settings}")
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

@app.route('/facebook-callback')
def facebook_callback():
    try:
        code = request.args.get('code')
        if not code:
            flash('Fehlender Autorisierungscode', 'error')
            return redirect(url_for('index'))

        settings = get_instagram_settings()
        
        # Token von Facebook erhalten
        token_url = 'https://graph.facebook.com/v18.0/oauth/access_token'
        token_data = {
            'client_id': settings['INSTAGRAM_CLIENT_ID'],
            'client_secret': settings['INSTAGRAM_CLIENT_SECRET'],
            'redirect_uri': request.base_url,
            'code': code
        }
        
        token_response = requests.post(token_url, data=token_data)
        token_response.raise_for_status()
        access_token = token_response.json().get('access_token')

        # Instagram Business Account ID abrufen
        accounts_url = 'https://graph.facebook.com/v18.0/me/accounts'
        accounts_response = requests.get(accounts_url, params={'access_token': access_token})
        accounts_response.raise_for_status()
        
        # Ersten Facebook Page ID nehmen
        page_id = accounts_response.json()['data'][0]['id']
        page_access_token = accounts_response.json()['data'][0]['access_token']

        # Instagram Business Account ID abrufen
        instagram_account_url = f'https://graph.facebook.com/v18.0/{page_id}?fields=instagram_business_account'
        instagram_response = requests.get(instagram_account_url, params={'access_token': page_access_token})
        instagram_response.raise_for_status()
        
        instagram_account_id = instagram_response.json()['instagram_business_account']['id']

        # Token in Session speichern
        session['access_token'] = access_token
        session['instagram_account_id'] = instagram_account_id
        
        flash('Erfolgreich mit Instagram verbunden!', 'success')
        return redirect(url_for('index'))

    except Exception as e:
        print(f"Error in callback: {str(e)}")
        flash(f'Fehler bei der Authentifizierung: {str(e)}', 'error')
        return redirect(url_for('index'))

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

if __name__ == '__main__':
    app.run(debug=True)