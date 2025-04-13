# app/routes/settings.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from app.tasks.monitor_task import monitor, run_immediate_check
from app.config import Config
import os
import time
import logging

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/')
def index():
    # Get settings from environment variables to ensure they're current
    env_polling_interval = os.environ.get('POLLING_INTERVAL')
    env_log_level = os.environ.get('LOG_LEVEL', 'INFO')
    
    settings = {
        'polling_interval': int(env_polling_interval) if env_polling_interval and env_polling_interval.isdigit() else Config.POLLING_INTERVAL,
        'max_retries': os.environ.get('MAX_RETRIES', Config.MAX_RETRIES),
        'retry_delay': os.environ.get('RETRY_DELAY', Config.RETRY_DELAY),
        'youtube_api_key': Config.YOUTUBE_API_KEY[:5] + '...' if Config.YOUTUBE_API_KEY else None,
        'log_level': env_log_level,
        'environment': os.environ.get('FLASK_ENV', 'development')
    }
    
    # Convert string values to integers
    for key in ['polling_interval', 'max_retries', 'retry_delay']:
        if isinstance(settings[key], str) and settings[key].isdigit():
            settings[key] = int(settings[key])
    
    current_app.logger.info(f"Settings page loaded with polling_interval: {settings['polling_interval']} (env value: {env_polling_interval})")
    
    return render_template('settings.html', settings=settings)

@settings_bp.route('/update', methods=['POST'])
def update():
    # Get all form inputs
    polling_interval = request.form.get('polling_interval', '')
    max_retries = request.form.get('max_retries', '')
    retry_delay = request.form.get('retry_delay', '')
    youtube_api_key = request.form.get('youtube_api_key', '')
    log_level = request.form.get('log_level', '')
    
    # Update polling interval if provided
    if polling_interval and polling_interval.isdigit():
        polling_interval = int(polling_interval)
        if polling_interval < 60:
            flash('Polling interval must be at least 60 seconds', 'error')
            return redirect(url_for('settings.index'))
            
        # Update all three places: Config, current_app.config, and environment
        Config.POLLING_INTERVAL = polling_interval
        current_app.config['POLLING_INTERVAL'] = polling_interval
        os.environ['POLLING_INTERVAL'] = str(polling_interval)
        current_app.logger.info(f"Updated POLLING_INTERVAL to {polling_interval} in Config, app config, and environment")
        
        # Force update to monitor task if it's running
        if hasattr(monitor, 'app') and monitor.app is not None:
            current_app.logger.info("Updating polling interval in running monitor task")
            try:
                # This just flags for the next cycle, doesn't affect current sleep
                monitor.app.config['POLLING_INTERVAL'] = polling_interval
            except Exception as e:
                current_app.logger.error(f"Error updating monitor task config: {e}")
    
    # Update max retries if provided
    if max_retries and max_retries.isdigit():
        max_retries = int(max_retries)
        if max_retries < 0 or max_retries > 10:
            flash('Max retries must be between 0 and 10', 'error')
            return redirect(url_for('settings.index'))
            
        Config.MAX_RETRIES = max_retries
        current_app.config['MAX_RETRIES'] = max_retries
        os.environ['MAX_RETRIES'] = str(max_retries)
        current_app.logger.info(f"Updated MAX_RETRIES environment variable to {max_retries}")
    
    # Update retry delay if provided
    if retry_delay and retry_delay.isdigit():
        retry_delay = int(retry_delay)
        if retry_delay < 10:
            flash('Retry delay must be at least 10 seconds', 'error')
            return redirect(url_for('settings.index'))
            
        Config.RETRY_DELAY = retry_delay
        current_app.config['RETRY_DELAY'] = retry_delay
        os.environ['RETRY_DELAY'] = str(retry_delay)
        current_app.logger.info(f"Updated RETRY_DELAY environment variable to {retry_delay}")
    
    # Update YouTube API key if provided
    if youtube_api_key:
        Config.YOUTUBE_API_KEY = youtube_api_key
        current_app.config['YOUTUBE_API_KEY'] = youtube_api_key
        os.environ['YOUTUBE_API_KEY'] = youtube_api_key
        current_app.logger.info("Updated YOUTUBE_API_KEY environment variable")
    
    # Update log level if provided
    if log_level:
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if log_level not in valid_levels:
            flash(f'Invalid log level. Must be one of: {", ".join(valid_levels)}', 'error')
            return redirect(url_for('settings.index'))
            
        Config.LOG_LEVEL = log_level
        current_app.config['LOG_LEVEL'] = log_level
        os.environ['LOG_LEVEL'] = log_level
        
        # Update the root logger level
        logging.getLogger().setLevel(getattr(logging, log_level))
        current_app.logger.setLevel(getattr(logging, log_level))
        current_app.logger.info(f"Updated LOG_LEVEL environment variable to {log_level}")
    
    # Log that settings were updated
    current_app.logger.info(f"Settings updated - Polling interval: {Config.POLLING_INTERVAL}, Max retries: {Config.MAX_RETRIES}, Retry delay: {Config.RETRY_DELAY}, Log level: {Config.LOG_LEVEL}")
    
    flash('Settings updated successfully', 'success')
    return redirect(url_for('settings.index'))

@settings_bp.route('/restart', methods=['POST'])
def restart_monitor():
    # Restart the monitoring task with the current settings
    monitor.stop()
    
    # Wait a moment to ensure the monitor has stopped
    time.sleep(1)
    
    # Log current settings before restart
    current_polling = current_app.config.get('POLLING_INTERVAL')
    env_polling = os.environ.get('POLLING_INTERVAL')
    
    current_app.logger.info(f"Restarting monitor with polling interval: {current_polling} seconds (env: {env_polling})")
    
    # Ensure the polling interval is synchronized
    if str(current_polling) != env_polling and current_polling is not None:
        os.environ['POLLING_INTERVAL'] = str(current_polling)
        current_app.logger.info(f"Updated environment POLLING_INTERVAL to match config: {current_polling}")
    
    # Start the monitoring task with current app
    monitor.start(current_app._get_current_object())
    
    # Run an immediate check to ensure all channels are checked right away
    current_app.logger.info("Running immediate check after restart")
    run_immediate_check(current_app._get_current_object())
    
    flash('Monitoring service restarted successfully and immediate check initiated', 'success')
    return redirect(url_for('settings.index'))

@settings_bp.route('/check_now', methods=['POST'])
def check_now():
    """Force an immediate check of all channels"""
    current_app.logger.info("Manual check triggered by user")
    
    # Run an immediate check
    run_immediate_check(current_app._get_current_object())
    
    flash('Manual channel check initiated', 'success')
    return redirect(url_for('settings.index'))

@settings_bp.route('/test_youtube_api')
def test_youtube_api():
    """Test the YouTube API connection"""
    try:
        from app.services.youtube_service import YouTubeService
        import requests
        import json
        
        # Get current settings to pass to the template
        env_polling_interval = os.environ.get('POLLING_INTERVAL')
        env_log_level = os.environ.get('LOG_LEVEL', 'INFO')
    
        settings = {
            'polling_interval': int(env_polling_interval) if env_polling_interval and env_polling_interval.isdigit() else Config.POLLING_INTERVAL,
            'max_retries': os.environ.get('MAX_RETRIES', Config.MAX_RETRIES),
            'retry_delay': os.environ.get('RETRY_DELAY', Config.RETRY_DELAY),
            'youtube_api_key': Config.YOUTUBE_API_KEY[:5] + '...' if Config.YOUTUBE_API_KEY else None,
            'log_level': env_log_level,
            'environment': os.environ.get('FLASK_ENV', 'development')
        }
        
        # Convert string values to integers
        for key in ['polling_interval', 'max_retries', 'retry_delay']:
            if isinstance(settings[key], str) and settings[key].isdigit():
                settings[key] = int(settings[key])
        
        api_key = current_app.config.get('YOUTUBE_API_KEY')
        
        if not api_key or api_key == 'YOUR_NEW_API_KEY_HERE':
            flash('YouTube API key is not set or is using the default placeholder value.', 'error')
            return render_template('settings.html', 
                                  settings=settings,
                                  api_status='error',
                                  api_message='API key not configured')
        
        # Use a simple YouTube API endpoint that doesn't consume much quota
        test_url = f"https://www.googleapis.com/youtube/v3/videos?part=id&chart=mostPopular&maxResults=1&key={api_key}"
        
        response = requests.get(test_url)
        
        if response.status_code == 200:
            # Success - API is working
            flash('YouTube API connection successful!', 'success')
            return render_template('settings.html', 
                                  settings=settings,
                                  api_status='success',
                                  api_message='API connection working correctly')
        elif response.status_code == 403:
            # Handle specific error cases
            error_data = response.json()
            error_reason = error_data.get('error', {}).get('errors', [{}])[0].get('reason', 'unknown')
            
            if error_reason == 'quotaExceeded':
                flash('YouTube API quota has been exceeded. Please wait until tomorrow or upgrade your Google Cloud project.', 'error')
                error_message = 'API quota exceeded'
            elif error_reason == 'keyInvalid':
                flash('The YouTube API key is invalid. Please check your key and make sure it\'s correctly configured.', 'error')
                error_message = 'Invalid API key'
            else:
                flash(f'YouTube API returned 403 Forbidden error. Reason: {error_reason}', 'error')
                error_message = f'Forbidden: {error_reason}'
                
            return render_template('settings.html', 
                                  settings=settings,
                                  api_status='error',
                                  api_message=error_message)
        else:
            # Other errors
            flash(f'YouTube API error: {response.status_code} - {response.reason}', 'error')
            return render_template('settings.html', 
                                  settings=settings,
                                  api_status='error',
                                  api_message=f'{response.status_code}: {response.reason}')
    
    except Exception as e:
        flash(f'Error testing YouTube API: {str(e)}', 'error')
        
        # Still provide settings to the template
        env_polling_interval = os.environ.get('POLLING_INTERVAL')
        env_log_level = os.environ.get('LOG_LEVEL', 'INFO')
    
        settings = {
            'polling_interval': int(env_polling_interval) if env_polling_interval and env_polling_interval.isdigit() else Config.POLLING_INTERVAL,
            'max_retries': os.environ.get('MAX_RETRIES', Config.MAX_RETRIES),
            'retry_delay': os.environ.get('RETRY_DELAY', Config.RETRY_DELAY),
            'youtube_api_key': Config.YOUTUBE_API_KEY[:5] + '...' if Config.YOUTUBE_API_KEY else None,
            'log_level': env_log_level,
            'environment': os.environ.get('FLASK_ENV', 'development')
        }
        
        # Convert string values to integers
        for key in ['polling_interval', 'max_retries', 'retry_delay']:
            if isinstance(settings[key], str) and settings[key].isdigit():
                settings[key] = int(settings[key])
        
        return render_template('settings.html', 
                              settings=settings,
                              api_status='error',
                              api_message=str(e))
