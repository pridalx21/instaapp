import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, jsonify
from datetime import datetime, timedelta
import json
from werkzeug.utils import secure_filename
import logging
import secrets
from functools import wraps
import requests
from PIL import Image
import io
import base64
import time
import random
from flask_sqlalchemy import SQLAlchemy

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)  # Generate a secure random key
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)  # Session expires after 1 day
app.config['DEBUG'] = False  # Disable debug mode in production
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size for videos
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instaapp.db'
db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    posts = db.relationship('Post', backref='author', lazy=True)
    subscription = db.relationship('Subscription', backref='user', uselist=False)

    def __init__(self, username, email):
        self.username = username
        self.email = email

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    image_url = db.Column(db.String(200), nullable=False)
    caption = db.Column(db.String(200), nullable=False)
    hashtags = db.Column(db.String(200), nullable=False)
    scheduled_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(50), nullable=False)

    def __init__(self, user_id, image_url, caption, hashtags, scheduled_time, status):
        self.user_id = user_id
        self.image_url = image_url
        self.caption = caption
        self.hashtags = hashtags
        self.scheduled_time = scheduled_time
        self.status = status

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    plan_type = db.Column(db.String(20), nullable=False)  # 'monthly', 'sixmonth', 'yearly'
    start_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    end_date = db.Column(db.DateTime, nullable=False)
    active = db.Column(db.Boolean, default=True)
    price = db.Column(db.Float, nullable=False)

    def __init__(self, user_id, plan_type, price):
        self.user_id = user_id
        self.plan_type = plan_type
        self.price = price
        self.start_date = datetime.utcnow()
        
        # Set end date based on plan type
        if plan_type == 'monthly':
            self.end_date = self.start_date + timedelta(days=30)
        elif plan_type == 'sixmonth':
            self.end_date = self.start_date + timedelta(days=180)
        elif plan_type == 'yearly':
            self.end_date = self.start_date + timedelta(days=365)

# Create tables on startup
with app.app_context():
    db.create_all()
    
    # Create test user if it doesn't exist
    test_user = User.query.filter_by(username='testuser').first()
    if not test_user:
        test_user = User(username='testuser', email='test@example.com')
        db.session.add(test_user)
        db.session.commit()
        app.logger.info('Test user created successfully!')
    
    app.logger.info('Database tables created successfully!')

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Logging konfigurieren
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# File Upload Configuration
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'mov', 'avi'}
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'wav', 'm4a'}

def allowed_file(filename, filetype):
    if not filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    if filetype == 'image':
        return ext in ALLOWED_IMAGE_EXTENSIONS
    elif filetype == 'video':
        return ext in ALLOWED_VIDEO_EXTENSIONS
    elif filetype == 'audio':
        return ext in ALLOWED_AUDIO_EXTENSIONS
    return False

# Post Configuration
POST_FORMATS = {
    'feed': {
        'name': 'Feed Post',
        'allowed_media': ['image', 'video'],
        'max_duration': 60, # seconds for video
        'aspect_ratios': ['1:1', '4:5', '16:9']
    },
    'reel': {
        'name': 'Reel',
        'allowed_media': ['video'],
        'max_duration': 90, # seconds
        'aspect_ratio': '9:16'
    },
    'story': {
        'name': 'Story',
        'allowed_media': ['image', 'video'],
        'max_duration': 15, # seconds for video
        'aspect_ratio': '9:16'
    },
    'carousel': {
        'name': 'Carousel',
        'allowed_media': ['image', 'video'],
        'max_items': 10,
        'aspect_ratios': ['1:1', '4:5', '16:9']
    }
}

# Fake user profile for testing
FAKE_PROFILE = {
    'username': 'test_user',
    'full_name': 'Test User',
    'profile_picture_url': 'https://via.placeholder.com/150',
    'bio': 'This is a test profile for local development',
    'media_count': 0,
    'media': {'data': []}
}

def validate_schedule_time(schedule_time):
    try:
        schedule_dt = datetime.fromisoformat(schedule_time)
        now = datetime.now()
        if schedule_dt <= now:
            return False, "Schedule time must be in the future"
        if schedule_dt > now + timedelta(days=30):
            return False, "Cannot schedule posts more than 30 days in advance"
        return True, None
    except ValueError:
        return False, "Invalid datetime format"

def calculate_statistics(posts):
    now = datetime.now()
    stats = {
        'total_posts': len(posts),
        'scheduled_posts': 0,
        'posts_this_month': 0,
        'posts_by_format': {
            'feed': 0,
            'reel': 0,
            'story': 0,
            'carousel': 0
        },
        'posts_by_type': {
            'IMAGE': 0,
            'VIDEO': 0
        },
        'upcoming_posts': [],
        'most_active_day': None,
        'posts_by_weekday': {
            'Montag': 0, 'Dienstag': 0, 'Mittwoch': 0,
            'Donnerstag': 0, 'Freitag': 0, 'Samstag': 0, 'Sonntag': 0
        }
    }

    if not posts:
        return stats

    # Posts by date for finding most active day
    posts_by_date = {}
    weekday_names = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']

    for post in posts:
        post_time = datetime.fromisoformat(post['timestamp'])
        
        # Count scheduled posts
        if post_time > now:
            stats['scheduled_posts'] += 1
            if len(stats['upcoming_posts']) < 5:  # Keep only next 5 upcoming posts
                stats['upcoming_posts'].append({
                    'timestamp': post_time,
                    'format': post['post_format'],
                    'type': post['media_type']
                })

        # Count posts this month
        if post_time.year == now.year and post_time.month == now.month:
            stats['posts_this_month'] += 1

        # Count by format
        stats['posts_by_format'][post['post_format']] += 1

        # Count by type
        stats['posts_by_type'][post['media_type']] += 1

        # Track posts by date for most active day
        date_key = post_time.date()
        posts_by_date[date_key] = posts_by_date.get(date_key, 0) + 1

        # Count posts by weekday
        weekday_name = weekday_names[post_time.weekday()]
        stats['posts_by_weekday'][weekday_name] += 1

    # Find most active day
    if posts_by_date:
        most_active_date = max(posts_by_date.items(), key=lambda x: x[1])[0]
        stats['most_active_day'] = {
            'date': most_active_date.strftime('%d.%m.%Y'),
            'count': posts_by_date[most_active_date]
        }

    # Sort upcoming posts by date
    stats['upcoming_posts'].sort(key=lambda x: x['timestamp'])

    return stats

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_info' not in session:
            flash('Bitte melden Sie sich zuerst an', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Hugging Face API Configuration
HUGGINGFACE_API_KEY = os.getenv('HUGGINGFACE_API_KEY')
HUGGINGFACE_API_URL = "https://api-inference.huggingface.co/models/"
TEXT_MODEL = "HuggingFaceH4/zephyr-7b-beta"  # Besseres Modell für Text-Generierung
IMAGE_MODEL = "stabilityai/stable-diffusion-xl-base-1.0"

headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}

def query_huggingface(payload, model):
    """Generic function to query Hugging Face API"""
    try:
        response = requests.post(
            f"{HUGGINGFACE_API_URL}{model}",
            headers=headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.json()
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error querying Hugging Face API: {str(e)}")
        raise Exception(f"API request failed: {str(e)}")

def generate_image_with_stable_diffusion(prompt):
    """Generate image using Stable Diffusion"""
    try:
        response = requests.post(
            f"{HUGGINGFACE_API_URL}{IMAGE_MODEL}",
            headers=headers,
            json={
                "inputs": prompt,
                "parameters": {
                    "negative_prompt": "blurry, bad quality, distorted, ugly, deformed",
                    "num_inference_steps": 30,
                    "guidance_scale": 7.5
                }
            },
            timeout=30
        )
        response.raise_for_status()
        
        # Die API gibt die Bilddaten direkt als Bytes zurück
        image_bytes = response.content
        
        # Konvertiere zu Base64
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        return f"data:image/jpeg;base64,{image_base64}"
    except Exception as e:
        app.logger.error(f"Error generating image: {str(e)}")
        raise

@app.route('/api/schedule-post', methods=['POST'])
@login_required
def api_schedule_post():
    try:
        data = request.json
        
        # Berechne optimalen Postzeitpunkt
        posting_time = calculate_optimal_posting_time(
            data['ageRange'],
            data['interests']
        )
        
        # Speichere den Post in der Datenbank
        new_post = Post(
            user_id=1, # current_user.id,
            image_url=data['imageUrl'],
            caption=data['caption'],
            hashtags=','.join(data['hashtags']),
            scheduled_time=posting_time,
            status='scheduled'
        )
        
        db.session.add(new_post)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'scheduledTime': posting_time.strftime('%Y-%m-%d %H:%M:%S'),
            'message': f'Post geplant für {posting_time.strftime("%d.%m.%Y um %H:%M")} Uhr'
        })
        
    except Exception as e:
        app.logger.error(f"Error scheduling post: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/generate_post', methods=['GET', 'POST'])
def generate_post_function():
    if request.method == 'POST':
        prompt = request.form.get('prompt')
        
        for attempt in range(10):  # Try 3 times
            try:
                response = query_huggingface({"inputs": prompt}, TEXT_MODEL)
                generated_post = response[0]['generated_text']
                return render_template('generate_post.html', generated_post=generated_post)
            except Exception as e:
                return render_template('generate_post.html', error=f"An error occurred: {str(e)}")
    
    return render_template('generate_post.html')

@app.route('/')
def index():
    if 'user_info' not in session:
        session['user_info'] = FAKE_PROFILE.copy()
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    user_info = session.get('user_info', FAKE_PROFILE.copy())
    posts = user_info.get('media', {}).get('data', [])
    
    # Calculate statistics
    statistics = calculate_statistics(posts)
    
    # Pass statistics to the template
    return render_template('dashboard.html', statistics=statistics)

@app.route('/scheduler')
@login_required
def scheduler():
    return render_template('scheduler.html')

@app.route('/schedule_posts', methods=['POST'])
def schedule_posts():
    try:
        if 'user_info' not in session:
            flash('Bitte melden Sie sich zuerst an', 'error')
            return redirect(url_for('index'))

        # Ensure upload directory exists
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

        captions = request.form.getlist('captions[]')
        schedules = request.form.getlist('schedules[]')
        post_types = request.form.getlist('post_types[]')
        post_formats = request.form.getlist('post_formats[]')
        media_files = request.files.getlist('media[]')
        audio_files = request.files.getlist('audio[]')

        if not all([captions, schedules, post_types, post_formats, media_files]):
            flash('Bitte füllen Sie alle erforderlichen Felder aus', 'error')
            return redirect(url_for('scheduler'))

        if len(captions) != len(schedules) or len(captions) != len(media_files) or len(captions) != len(post_types):
            flash('Ungültige Anzahl von Medien, Bildunterschriften oder Zeitpunkten', 'error')
            return redirect(url_for('scheduler'))

        user_info = session.get('user_info', FAKE_PROFILE.copy())
        if 'media' not in user_info:
            user_info['media'] = {'data': []}

        successful_posts = 0
        for caption, schedule, post_type, post_format, media_file, audio_file in zip(captions, schedules, post_types, post_formats, media_files, audio_files):
            try:
                # Validate schedule time
                schedule_dt = datetime.fromisoformat(schedule)
                now = datetime.now()
                if schedule_dt <= now:
                    flash(f'Zeitpunkt muss in der Zukunft liegen: {schedule}', 'error')
                    continue

                # Validate post format and media type combination
                if post_format not in POST_FORMATS:
                    flash(f'Ungültiges Post-Format: {post_format}', 'error')
                    continue

                format_config = POST_FORMATS[post_format]
                if post_type not in format_config['allowed_media']:
                    flash(f'{format_config["name"]} unterstützt keine {post_type}-Dateien', 'error')
                    continue

                # Validate and save media file
                if not media_file or not allowed_file(media_file.filename, post_type):
                    allowed_types = {
                        'image': ', '.join(ALLOWED_IMAGE_EXTENSIONS),
                        'video': ', '.join(ALLOWED_VIDEO_EXTENSIONS)
                    }
                    flash(f'Ungültiges Dateiformat für {post_type}. Erlaubte Formate: {allowed_types.get(post_type)}', 'error')
                    continue

                # Save media file
                if media_file and media_file.filename:
                    media_filename = secure_filename(media_file.filename)
                    media_filepath = os.path.join(app.config['UPLOAD_FOLDER'], media_filename)
                    try:
                        media_file.save(media_filepath)
                    except Exception as e:
                        logger.error(f'Fehler beim Speichern der Mediendatei: {str(e)}')
                        flash(f'Fehler beim Speichern der Mediendatei: {media_file.filename}', 'error')
                        continue

                # Handle audio file if present
                audio_url = None
                if audio_file and audio_file.filename:
                    if not allowed_file(audio_file.filename, 'audio'):
                        flash(f'Ungültiges Audio-Format. Erlaubte Formate: {", ".join(ALLOWED_AUDIO_EXTENSIONS)}', 'error')
                        continue
                    
                    audio_filename = secure_filename(audio_file.filename)
                    audio_filepath = os.path.join(app.config['UPLOAD_FOLDER'], audio_filename)
                    try:
                        audio_file.save(audio_filepath)
                        audio_url = url_for('static', filename=f'uploads/{audio_filename}')
                    except Exception as e:
                        logger.error(f'Fehler beim Speichern der Audiodatei: {str(e)}')
                        flash(f'Fehler beim Speichern der Audiodatei: {audio_file.filename}', 'error')
                        continue

                # Add to user media
                new_post = {
                    'id': str(len(user_info['media']['data']) + 1),
                    'caption': caption,
                    'media_type': post_type.upper(),
                    'post_format': post_format,
                    'media_url': url_for('static', filename=f'uploads/{media_filename}'),
                    'thumbnail_url': url_for('static', filename=f'uploads/{media_filename}'),
                    'audio_url': audio_url,
                    'permalink': '#',
                    'timestamp': schedule
                }

                user_info['media']['data'].append(new_post)
                successful_posts += 1

            except Exception as e:
                logger.error(f'Fehler beim Verarbeiten des Posts: {str(e)}')
                flash(f'Fehler beim Verarbeiten eines Posts: {str(e)}', 'error')
                continue

        if successful_posts > 0:
            user_info['media_count'] = len(user_info['media']['data'])
            session['user_info'] = user_info
            flash(f'{successful_posts} {"Post wurde" if successful_posts == 1 else "Posts wurden"} erfolgreich geplant', 'success')
        else:
            flash('Keine Posts konnten geplant werden', 'error')

        return redirect(url_for('dashboard'))

    except Exception as e:
        logger.error(f'Fehler beim Planen der Posts: {str(e)}')
        flash(f'Fehler beim Planen der Posts: {str(e)}', 'error')
        return redirect(url_for('scheduler'))

@app.route('/schedule_post', methods=['POST'])
def schedule_post():
    try:
        logger.debug('Received schedule_post request')
        logger.debug(f'Form data: {request.form}')
        logger.debug(f'Files: {request.files}')
        
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
            logger.debug(f'Saving image to: {filepath}')
            file.save(filepath)
            
            if 'user_info' not in session:
                session['user_info'] = FAKE_PROFILE.copy()
            user_info = session['user_info']
            
            # Initialisiere media Dictionary falls es noch nicht existiert
            if 'media' not in user_info:
                user_info['media'] = {'data': []}
            
            caption = request.form.get('caption', '')
            schedule_time = request.form.get('schedule')
            
            # Validate schedule time
            is_valid, error_msg = validate_schedule_time(schedule_time)
            if not is_valid:
                flash(error_msg, 'error')
                return redirect(url_for('scheduler'))
            
            new_post = {
                'id': str(len(user_info['media']['data']) + 1),
                'caption': caption,
                'media_type': 'IMAGE',
                'media_url': url_for('static', filename=f'uploads/{filename}'),
                'thumbnail_url': url_for('static', filename=f'uploads/{filename}'),
                'permalink': '#',
                'timestamp': schedule_time
            }
            
            user_info['media']['data'].append(new_post)
            user_info['media_count'] = len(user_info['media']['data'])
            session['user_info'] = user_info
            logger.debug('Post added to user_info')

            flash('Beitrag erfolgreich geplant!', 'success')
            return redirect(url_for('dashboard'))

        flash('Ungültiger Dateityp', 'error')
        return redirect(url_for('scheduler'))
        
    except Exception as e:
        logger.error(f'Error in schedule_post: {str(e)}', exc_info=True)
        flash(f'Fehler beim Planen des Beitrags: {str(e)}', 'error')
        return redirect(url_for('scheduler'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Username and password are required', 'error')
            return redirect(url_for('index'))
            
        # For demo purposes, using fake profile
        # In production, this should validate against a secure database
        if username == 'test_user':
            session['user_info'] = FAKE_PROFILE.copy()
            flash('Successfully logged in', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials', 'error')
            return redirect(url_for('index'))
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Sie wurden erfolgreich abgemeldet', 'success')
    return redirect(url_for('login'))

@app.errorhandler(413)
def too_large(e):
    flash('File is too large. Maximum size is 100MB.', 'error')
    return redirect(url_for('scheduler'))

@app.errorhandler(500)
def internal_error(e):
    logger.error(f'Internal Server Error: {str(e)}')
    flash('An internal error occurred. Please try again later.', 'error')
    return redirect(url_for('index'))

@app.route('/data-deletion')
def data_deletion():
    return render_template('data_deletion.html')

@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy-policy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/calendar')
@login_required
def calendar():
    user_info = session.get('user_info', FAKE_PROFILE.copy())
    posts = user_info.get('media', {}).get('data', [])
    
    # Group posts by date for calendar view
    posts_by_date = {}
    for post in posts:
        schedule_time = datetime.fromisoformat(post['timestamp'])
        date_key = schedule_time.date().isoformat()
        if date_key not in posts_by_date:
            posts_by_date[date_key] = []
        posts_by_date[date_key].append({
            **post,
            'time': schedule_time.strftime('%H:%M'),
            'format_name': POST_FORMATS[post['post_format']]['name']
        })

    return render_template('calendar.html', 
                         user_info=user_info,
                         posts_by_date=posts_by_date,
                         current_month=datetime.now().strftime('%Y-%m'))

@app.route('/analytics')
@login_required
def analytics():
    return render_template('analytics.html')

@app.route('/targeting')
@login_required
def targeting():
    return render_template('targeting.html')

@app.route('/api/generate-content', methods=['POST'])
@login_required
def generate_content():
    if not HUGGINGFACE_API_KEY:
        app.logger.error("Hugging Face API key is missing")
        return jsonify({'error': 'Hugging Face API key is not configured'}), 500
    
    try:
        data = request.json
        app.logger.info(f"Received content generation request: {data}")
        
        required_fields = ['contentType', 'tone', 'interests', 'ageRange']
        if not all(field in data for field in required_fields):
            missing_fields = [field for field in required_fields if field not in data]
            app.logger.error(f"Missing required fields: {missing_fields}")
            return jsonify({'error': f'Missing required fields: {missing_fields}'}), 400
        
        try:
            # Generate image prompt
            app.logger.info("Generating image prompt...")
            image_prompt = generate_image_prompt(data)
            app.logger.info(f"Generated image prompt: {image_prompt}")
            
            # Generate image
            app.logger.info("Generating image with Stable Diffusion...")
            image_url = generate_image_with_stable_diffusion(image_prompt)
            app.logger.info("Successfully generated image")
            
            # Generate caption and hashtags
            app.logger.info("Generating text content...")
            content = generate_text_content(data)
            app.logger.info("Successfully generated text content")
            
            return jsonify({
                'imageUrl': image_url,
                'caption': content['caption'],
                'hashtags': content['hashtags']
            })
            
        except Exception as e:
            app.logger.error(f"Error during content generation: {str(e)}")
            return jsonify({'error': str(e)}), 500
            
    except Exception as e:
        app.logger.error(f"Error processing request: {str(e)}")
        return jsonify({'error': f'Invalid request format: {str(e)}'}), 400

def generate_image_prompt(data):
    """Generate image prompt using Zephyr"""
    system_prompt = """You are an expert at creating detailed image generation prompts that result in high-quality, 
    Instagram-worthy images. Create a prompt that will generate a visually striking and professional image."""
    
    user_prompt = f"""Create a detailed image generation prompt for a {data['contentType']} post.
    Target audience: {data['ageRange']} year olds
    Interests: {', '.join(data['interests'])}
    Tone: {data['tone']}
    
    The image should be:
    - Visually striking and attention-grabbing
    - Well-composed with good lighting
    - Suitable for Instagram's square format
    - Authentic and relatable
    - Professional quality
    
    Provide only the image generation prompt, nothing else."""
    
    try:
        response = query_huggingface({
            "inputs": f"{system_prompt}\n\nUser: {user_prompt}\n\nAssistant:",
            "parameters": {
                "max_new_tokens": 100,
                "temperature": 0.7,
                "top_p": 0.95,
                "return_full_text": False
            }
        }, TEXT_MODEL)
        
        # Clean up the response
        prompt = response[0]['generated_text'].strip()
        return prompt
        
    except Exception as e:
        app.logger.error(f"Error generating image prompt: {str(e)}")
        raise

def generate_text_content(data):
    """Generate caption and hashtags using Zephyr"""
    system_prompt = """You are an expert Instagram content creator who writes engaging captions and selects trending hashtags.
    Your responses should be in valid JSON format with 'caption' and 'hashtags' fields."""
    
    user_prompt = f"""Create an Instagram post caption and hashtags for a {data['contentType']} post.
    
    Target Audience:
    - Age Range: {data['ageRange']}
    - Interests: {', '.join(data['interests'])}
    - Tone: {data['tone']}
    
    Requirements:
    1. Caption should be engaging and authentic
    2. Include emojis where appropriate
    3. Use line breaks for readability
    4. Include a call-to-action
    5. Generate 10-15 relevant hashtags
    
    Format the response as JSON:
    {{
        "caption": "Your caption here",
        "hashtags": ["hashtag1", "hashtag2"]
    }}"""
    
    try:
        response = query_huggingface({
            "inputs": f"{system_prompt}\n\nUser: {user_prompt}\n\nAssistant:",
            "parameters": {
                "max_new_tokens": 250,
                "temperature": 0.7,
                "top_p": 0.95,
                "return_full_text": False
            }
        }, TEXT_MODEL)
        
        # Extract JSON from the response
        response_text = response[0]['generated_text']
        
        # Find JSON in the response
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        
        if json_start == -1 or json_end == 0:
            # Fallback wenn kein JSON gefunden wurde
            return {
                'caption': response_text.strip(),
                'hashtags': []
            }
            
        json_str = response_text[json_start:json_end]
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Fallback wenn JSON ungültig ist
            return {
                'caption': response_text.strip(),
                'hashtags': []
            }
            
    except Exception as e:
        app.logger.error(f"Error generating text content: {str(e)}")
        raise

def calculate_optimal_posting_time(target_age, interests):
    """
    Berechnet den optimalen Posting-Zeitpunkt basierend auf der Zielgruppe
    """
    # Basis-Zeitfenster für verschiedene Altersgruppen
    age_windows = {
        "13-17": [(15, 17), (19, 21)],  # Nachmittag nach Schule und früher Abend
        "18-24": [(12, 14), (20, 23)],  # Mittagspause und später Abend
        "25-34": [(11, 13), (19, 21)],  # Mittagspause und nach Arbeit
        "35-44": [(9, 11), (20, 22)],   # Vormittag und Abend
        "45+": [(8, 10), (19, 21)]      # Früher Morgen und früher Abend
    }
    
    # Interessen-basierte Anpassungen (in Stunden)
    interest_adjustments = {
        "Mode & Beauty": 1,      # Eher später am Tag
        "Fitness & Gesundheit": -2,  # Eher früher am Tag
        "Reisen & Abenteuer": 0,
        "Essen & Kochen": -1,    # Eher zur Essenszeit
        "Technologie": 2,        # Eher später am Tag
        "Business": -3           # Eher während Arbeitszeit
    }
    
    # Standardzeitfenster falls Alter nicht erkannt
    age_range = "18-24"
    for age_key in age_windows.keys():
        if age_key in target_age:
            age_range = age_key
            break
    
    # Wähle zufälliges Zeitfenster für den Tag
    time_windows = age_windows[age_range]
    selected_window = random.choice(time_windows)
    
    # Berechne Durchschnitt der Interessens-Anpassungen
    total_adjustment = 0
    for interest in interests:
        if interest in interest_adjustments:
            total_adjustment += interest_adjustments[interest]
    avg_adjustment = total_adjustment / len(interests) if interests else 0
    
    # Berechne optimale Stunde innerhalb des Zeitfensters
    start_hour, end_hour = selected_window
    target_hour = min(max(start_hour + avg_adjustment, start_hour), end_hour)
    
    # Setze Datum auf morgen
    tomorrow = datetime.now() + timedelta(days=1)
    posting_time = tomorrow.replace(
        hour=int(target_hour),
        minute=random.randint(0, 59),
        second=0,
        microsecond=0
    )
    
    return posting_time

@app.route('/scheduled_posts', methods=['GET', 'POST'])
def scheduled_posts():
    # Lade alle geplanten Posts aus der Datenbank
    posts = Post.query.filter_by(status='scheduled').all()
    
    # Formatiere die Posts für den Kalender
    events = []
    for post in posts:
        events.append({
            'id': post.id,
            'title': post.caption[:30] + '...' if len(post.caption) > 30 else post.caption,
            'start': post.scheduled_time.strftime('%Y-%m-%d %H:%M:%S'),
            'end': (post.scheduled_time + timedelta(minutes=30)).strftime('%Y-%m-%d %H:%M:%S'),
            'imageUrl': post.image_url,
            'caption': post.caption,
            'hashtags': post.hashtags.split(',')
        })
    
    return render_template('scheduled_posts.html', events=events)

@app.route('/pricing')
def pricing():
    return render_template('pricing.html')

@app.route('/api/subscribe', methods=['POST'])
@login_required
def subscribe():
    data = request.json
    plan_type = data.get('plan')
    price = data.get('price')
    
    if not plan_type or not price:
        return jsonify({'success': False, 'error': 'Invalid plan data'})
    
    try:
        # Create new subscription
        subscription = Subscription(
            user_id=session['user_id'],
            plan_type=plan_type,
            price=price
        )
        db.session.add(subscription)
        db.session.commit()
        
        # Here you would typically redirect to a payment processor
        # For now, we'll just redirect to the dashboard
        return jsonify({
            'success': True,
            'redirect_url': url_for('dashboard')
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    # Use production server when deployed
    if os.environ.get('RENDER'):
        app.run()
    else:
        # Use debug mode locally
        app.run(debug=True)