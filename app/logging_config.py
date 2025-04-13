# app/logging_config.py

import os
import logging
from logging.handlers import RotatingFileHandler

def configure_logging(app):
    """Configure logging for the application"""
    
    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(app.root_path, '..', 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    # Set up file handler
    file_handler = RotatingFileHandler(
        os.path.join(logs_dir, 'youtube_monitor.log'),
        maxBytes=10485760,  # 10MB
        backupCount=10
    )
    
    # Set formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    
    # Set log level from config
    log_level = app.config.get('LOG_LEVEL', 'INFO')
    file_handler.setLevel(getattr(logging, log_level))
    
    # Add handler to app logger
    app.logger.addHandler(file_handler)
    
    # Set root logger level
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    root_logger.addHandler(file_handler)
    
    # Add console handler in development
    if app.debug:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(getattr(logging, log_level))
        app.logger.addHandler(console_handler)
        root_logger.addHandler(console_handler)
    
    app.logger.info('Logging configured')
