# run.py
from flask import Flask, render_template, redirect, url_for
from app.config import config
from app.routes.dashboard import dashboard_bp
from app.routes.channels import channels_bp 
from app.routes.webhooks import webhooks_bp
from app.routes.settings import settings_bp
from app import create_app, mongo

# Initialize the Flask application
app = create_app()

if __name__ == '__main__':
    # Run with simple Flask development server
    app.run(host='0.0.0.0', port=5000, debug=True)
