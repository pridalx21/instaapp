# InstaApp - Instagram Post Manager

Ein professioneller Instagram Post Manager mit KI-gestützter Inhaltsgenerierung und automatischer Planung.

## Features

- 🤖 KI-gestützte Bildgenerierung mit Stable Diffusion
- 📝 Automatische Hashtag- und Caption-Generierung
- 📅 Intelligente Posting-Zeitplanung
- 📊 Performance-Analyse und Statistiken
- 🔐 Sicherer Facebook/Instagram Login
- 💼 Verschiedene Abonnement-Optionen

## Technologie-Stack

- **Backend**: Python/Flask
- **Datenbank**: SQLite (Entwicklung) / PostgreSQL (Produktion)
- **KI-Modelle**: Hugging Face (Zephyr, Stable Diffusion)
- **Authentifizierung**: Facebook OAuth
- **Hosting**: Render.com

## Installation

1. Repository klonen:
   ```bash
   git clone https://github.com/pridalx21/instaapp.git
   cd instaapp
   ```

2. Virtuelle Umgebung erstellen und aktivieren:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   source .venv/bin/activate  # Linux/Mac
   ```

3. Abhängigkeiten installieren:
   ```bash
   pip install -r requirements.txt
   ```

4. Umgebungsvariablen konfigurieren:
   ```bash
   # .env Datei erstellen mit:
   FLASK_APP=app.py
   FLASK_ENV=development
   SECRET_KEY=your_secret_key
   FACEBOOK_APP_ID=your_app_id
   FACEBOOK_APP_SECRET=your_app_secret
   HUGGINGFACE_API_KEY=your_api_key
   ```

5. Datenbank initialisieren:
   ```bash
   flask db upgrade
   ```

6. Server starten:
   ```bash
   flask run
   ```

## Deployment

Die Anwendung ist für das Deployment auf Render.com konfiguriert. Folgende Umgebungsvariablen müssen gesetzt werden:

- `DATABASE_URL`: PostgreSQL Datenbank URL
- `FACEBOOK_APP_ID`: Facebook App ID
- `FACEBOOK_APP_SECRET`: Facebook App Secret
- `HUGGINGFACE_API_KEY`: Hugging Face API Key
- `SECRET_KEY`: Flask Secret Key
- `FLASK_ENV`: production

## Lizenz

 2024 Mischa Pridal. Alle Rechte vorbehalten.
