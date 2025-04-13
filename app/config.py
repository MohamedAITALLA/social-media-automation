# app/config.py

import os
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')
    MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/youtube_monitor')
    
    # Get the YouTube API key and log its value (partially masked for security)
    YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY', '')
    if YOUTUBE_API_KEY:
        masked_key = YOUTUBE_API_KEY[:6] + '*****' + YOUTUBE_API_KEY[-4:] if len(YOUTUBE_API_KEY) > 10 else '******'
        logger.info(f"Loaded YouTube API key from environment: {masked_key}")
    else:
        logger.error("No YouTube API key found in environment variables")
        
    POLLING_INTERVAL = int(os.environ.get('POLLING_INTERVAL', 3600))  # Default: 1 hour
    MAX_RETRIES = int(os.environ.get('MAX_RETRIES', 3))
    RETRY_DELAY = int(os.environ.get('RETRY_DELAY', 300))  # Default: 5 minutes
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # Socket.IO settings
    SOCKETIO_ASYNC_MODE = os.environ.get('SOCKETIO_ASYNC_MODE', 'eventlet')
    
    # Security settings
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    
    @classmethod
    def init_app(cls, app):
        """Initialize application with configuration"""
        pass

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    LOG_LEVEL = 'DEBUG'

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    MONGO_URI = 'mongodb://localhost:27017/youtube_monitor_test'
    LOG_LEVEL = 'DEBUG'

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'WARNING')
    SESSION_COOKIE_SECURE = True
    
    # In production, ensure SECRET_KEY is set
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        
        if not os.environ.get('SECRET_KEY'):
            app.logger.error("SECRET_KEY environment variable not set in production!")
        
        if not os.environ.get('YOUTUBE_API_KEY'):
            app.logger.error("YOUTUBE_API_KEY environment variable not set!")

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
