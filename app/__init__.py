# app/__init__.py
from flask import Flask
from flask_pymongo import PyMongo
from flask_socketio import SocketIO
from app.config import config
from dotenv import load_dotenv
import os
import logging

# Load environment variables from .env file
load_dotenv()

# Create a single instance of PyMongo to be used throughout the app
mongo = PyMongo()
socketio = SocketIO(cors_allowed_origins="*", async_mode=None)

def create_app(config_name=None):
    """Create and configure the Flask application"""
    
    app = Flask(__name__)
    
    # Determine configuration to use
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
    
    # Apply configuration
    app.config.from_object(config[config_name])
    
    # Setup MongoDB with direct URI
    mongo_uri = os.environ.get('MONGO_URI')
    if mongo_uri:
        # For Vercel, ensure we handle connection properly
        app.config['MONGO_URI'] = mongo_uri
        app.config['MONGO_CONNECT'] = False  # Connect on first use instead of on initialization
        mongo.init_app(app)
        app.logger.info("MongoDB initialized successfully")
    else:
        app.logger.error("MONGO_URI environment variable is not set!")
    
    # Initialize SocketIO safely - for Vercel we'll limit some functionality
    try:
        # In serverless env, use threading mode instead of eventlet/gevent
        socketio_mode = "threading" if os.environ.get('VERCEL', False) else os.environ.get('SOCKETIO_ASYNC_MODE', 'eventlet')
        socketio.init_app(app, async_mode=socketio_mode, cors_allowed_origins="*")
        app.logger.info(f"SocketIO initialized successfully with mode: {socketio_mode}")
    except Exception as e:
        app.logger.warning(f"Failed to initialize SocketIO: {str(e)}")
    
    # Register blueprints
    from app.routes.dashboard import dashboard_bp
    from app.routes.channels import channels_bp
    from app.routes.webhooks import webhooks_bp
    from app.routes.settings import settings_bp
    
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(channels_bp, url_prefix='/channels')
    app.register_blueprint(webhooks_bp, url_prefix='/webhooks')
    app.register_blueprint(settings_bp, url_prefix='/settings')
    
    # Initialize app-specific configurations if any
    if hasattr(config[config_name], 'init_app'):
        config[config_name].init_app(app)
    
    # Setup logging
    from app.logging_config import configure_logging
    configure_logging(app)
    
    # Setup monitoring task - disable in Vercel environment
    if not os.environ.get('VERCEL', False):
        try:
            from app.tasks.monitor_task import setup_monitor
            setup_monitor(app)
            app.logger.info("Monitoring task setup completed")
        except Exception as e:
            app.logger.warning(f"Failed to setup monitoring task: {str(e)}")
    else:
        app.logger.info("Running in Vercel environment - monitoring tasks disabled")
    
    # Add template context processor for date/time formatting
    @app.context_processor
    def inject_datetime():
        from datetime import datetime, timedelta
        return {
            'now': datetime.now(),
            'datetime': datetime,
            'timedelta': timedelta
        }
    
    return app
