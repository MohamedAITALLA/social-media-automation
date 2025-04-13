# app/routes/dashboard.py (updated)

from flask import Blueprint, render_template, current_app, redirect, url_for, flash
from app import mongo
from app.models.system_event import SystemEvent
from app.tasks.monitor_task import monitor
from datetime import datetime, timedelta
import requests
import os
from dotenv import load_dotenv

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
def index():
    # Initialize default values
    stats = {
        'total_channels': 0,
        'active_channels': 0,
        'total_videos': 0,
        'videos_last_24h': 0,
        'total_webhooks': 0,
        'active_webhooks': 0
    }
    
    recent_videos = []
    system_events = []
    last_check = None
    channels = []
    
    # Check if mongo.db is available
    if mongo.db is not None:
        try:
            # Get channel stats
            stats['total_channels'] = mongo.db.channels.count_documents({})
            stats['active_channels'] = mongo.db.channels.count_documents({'active': True})
            
            # Get video stats
            stats['total_videos'] = mongo.db.videos.count_documents({})
            stats['videos_last_24h'] = mongo.db.videos.count_documents({
                'detected_at': {'$gte': datetime.utcnow() - timedelta(days=1)}
            })
            
            # Get webhook stats
            stats['total_webhooks'] = mongo.db.webhooks.count_documents({})
            stats['active_webhooks'] = mongo.db.webhooks.count_documents({'active': True})
            
            # Get recent videos
            recent_videos = list(mongo.db.videos.find().sort('detected_at', -1).limit(5))
            
            # Get recent events
            system_events = SystemEvent.get_recent_events(limit=5)
            
            # Get channels for the table
            channels = list(mongo.db.channels.find().limit(5))
            
            # Get last check time
            try:
                last_check = None
                
                # First try to get the last check time from system events
                check_event = mongo.db.system_events.find_one(
                    {'type': 'CHANNEL_CHECK'},
                    sort=[('timestamp', -1)]
                )
                
                if check_event and 'timestamp' in check_event:
                    last_check = check_event['timestamp']
                    current_app.logger.info(f"Found last check timestamp from system events: {last_check}")
                else:
                    # Fall back to channel's last_checked timestamp
                    last_check_doc = mongo.db.channels.find_one(
                        {'last_checked': {'$exists': True}},
                        sort=[('last_checked', -1)]
                    )
                    
                    if last_check_doc and 'last_checked' in last_check_doc:
                        last_check = last_check_doc['last_checked']
                        current_app.logger.info(f"Found last_checked timestamp from channels: {last_check}")
                    else:
                        # As a final fallback, check for any system event related to channel checks
                        check_event = mongo.db.system_events.find_one(
                            {'message': {'$regex': 'Checking channel', '$options': 'i'}},
                            sort=[('timestamp', -1)]
                        )
                        if check_event:
                            last_check = check_event['timestamp']
                            current_app.logger.info(f"Using system event timestamp as fallback: {last_check}")
                        else:
                            last_check = None
                            current_app.logger.warning("No last check timestamp found")
            except Exception as e:
                current_app.logger.error(f"Error getting last check time: {str(e)}")
                last_check = None
        except Exception as e:
            current_app.logger.error(f"Error accessing MongoDB: {str(e)}")
    else:
        current_app.logger.error("MongoDB connection is not available")

    # Check monitor status
    monitor_active = monitor.running
    
    # Check API key validity
    api_key_valid = False
    api_key_status = "Missing"
    api_key_details = "No YouTube API key configured"
    
    try:
        # First try to get API key from app config
        api_key = current_app.config.get('YOUTUBE_API_KEY')
        
        # If not found in app config, try getting it directly from environment
        if not api_key:
            # Load environment variables from .env file
            load_dotenv()
            
            # Check if environment has the key now
            api_key = os.environ.get('YOUTUBE_API_KEY')
            current_app.logger.info(f"API key from environment: {'Found' if api_key else 'Not found'}")
            
            # Update the app config if we found a key in the environment
            if api_key:
                current_app.config['YOUTUBE_API_KEY'] = api_key
                current_app.logger.info("Updated app config with API key from environment")
        
        if not api_key:
            api_key_status = "Missing"
            api_key_details = "No YouTube API key configured in environment variables"
        else:
            # Make a simple API request to test the key
            try:
                test_url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&chart=mostPopular&maxResults=1&key={api_key}"
                response = requests.get(test_url, timeout=10)
                
                if response.status_code == 200:
                    api_key_valid = True
                    api_key_status = "Valid"
                    api_key_details = "API key is working correctly"
                elif response.status_code == 400:
                    # Get detailed error information
                    try:
                        error_data = response.json()
                        error_message = error_data.get('error', {}).get('message', '')
                        error_reason = error_data.get('error', {}).get('errors', [{}])[0].get('reason', '')
                        
                        api_key_status = "Error"
                        api_key_details = f"Bad Request: {error_message} ({error_reason})"
                        current_app.logger.error(f"API Error: {error_data}")
                    except Exception as e:
                        api_key_status = "Error"
                        api_key_details = f"Bad Request (400): {str(e)}"
                elif response.status_code == 403:
                    # Check if this is a quota exceeded error
                    try:
                        error_data = response.json()
                        error_reason = error_data.get('error', {}).get('errors', [{}])[0].get('reason', '')
                        error_message = error_data.get('error', {}).get('message', '')
                        
                        if error_reason == 'quotaExceeded':
                            api_key_status = "Quota Exceeded"
                            api_key_details = "API key is valid but daily quota has been reached"
                        elif error_reason == 'keyInvalid':
                            api_key_status = "Invalid"
                            api_key_details = "API key is not valid or has been revoked"
                        else:
                            api_key_status = "Error"
                            api_key_details = f"API returned 403 error: {error_message} ({error_reason})"
                        
                        current_app.logger.error(f"API Error: {error_data}")
                    except Exception as e:
                        api_key_status = "Error"
                        api_key_details = f"Access Denied (403): {str(e)}"
                else:
                    api_key_status = "Error"
                    api_key_details = f"API returned unexpected status code: {response.status_code}"
                    # Try to log the response content
                    try:
                        current_app.logger.error(f"API Response: {response.text[:500]}")
                    except:
                        pass
            except requests.exceptions.RequestException as e:
                api_key_status = "Error"
                api_key_details = f"Connection error: {str(e)}"
    except Exception as e:
        current_app.logger.error(f"Error checking YouTube API key: {str(e)}")
        api_key_status = "Error"
        api_key_details = f"Unexpected error: {str(e)}"
    
    # Get settings
    settings = {
        'polling_interval': current_app.config.get('POLLING_INTERVAL', 3600),
        'max_retries': current_app.config.get('MAX_RETRIES', 3),
        'retry_delay': current_app.config.get('RETRY_DELAY', 300)
    }
    
    return render_template(
        'dashboard.html',
        stats=stats,
        recent_videos=recent_videos,
        system_events=system_events,
        monitor_active=monitor_active,
        last_check=last_check,
        api_key_valid=api_key_valid,
        api_key_status=api_key_status,
        api_key_details=api_key_details,
        settings=settings,
        mongo_available=mongo.db is not None,
        channels=channels,
        now=datetime.utcnow(),
        timedelta=timedelta
    )

@dashboard_bp.route('/test-api-key', methods=['POST'])
def test_api_key():
    """Endpoint to test the YouTube API key and refresh status"""
    try:
        # First try to get API key from app config
        api_key = current_app.config.get('YOUTUBE_API_KEY')
        
        # If not found in app config, try getting it directly from environment
        if not api_key:
            # Load environment variables from .env file
            load_dotenv()
            
            # Check if environment has the key now
            api_key = os.environ.get('YOUTUBE_API_KEY')
            current_app.logger.info(f"API key from environment: {'Found' if api_key else 'Not found'}")
            
            # Update the app config if we found a key in the environment
            if api_key:
                current_app.config['YOUTUBE_API_KEY'] = api_key
                current_app.logger.info("Updated app config with API key from environment")
        
        if not api_key:
            flash("No YouTube API key configured in environment variables", "error")
        else:
            # Make a simple API request to test the key
            try:
                test_url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&chart=mostPopular&maxResults=1&key={api_key}"
                response = requests.get(test_url, timeout=10)
                
                if response.status_code == 200:
                    flash("API key is working correctly", "success")
                elif response.status_code == 400:
                    # Get detailed error information
                    try:
                        error_data = response.json()
                        error_message = error_data.get('error', {}).get('message', '')
                        error_reason = error_data.get('error', {}).get('errors', [{}])[0].get('reason', '')
                        
                        flash(f"Bad Request: {error_message} ({error_reason})", "error")
                        current_app.logger.error(f"API Error: {error_data}")
                    except Exception as e:
                        flash(f"Bad Request (400): {str(e)}", "error")
                elif response.status_code == 403:
                    # Check if this is a quota exceeded error
                    try:
                        error_data = response.json()
                        error_reason = error_data.get('error', {}).get('errors', [{}])[0].get('reason', '')
                        error_message = error_data.get('error', {}).get('message', '')
                        
                        if error_reason == 'quotaExceeded':
                            flash("API key is valid but daily quota has been reached", "warning")
                        elif error_reason == 'keyInvalid':
                            flash("API key is not valid or has been revoked", "error")
                        else:
                            flash(f"API returned 403 error: {error_message} ({error_reason})", "error")
                        current_app.logger.error(f"API Error: {error_data}")
                    except Exception as e:
                        flash(f"Access Denied (403): {str(e)}", "error")
                else:
                    flash(f"API returned unexpected status code: {response.status_code}", "error")
                    # Try to log the response content
                    try:
                        current_app.logger.error(f"API Response: {response.text[:500]}")
                    except:
                        pass
            except requests.exceptions.RequestException as e:
                flash(f"Connection error: {str(e)}", "error")
    except Exception as e:
        current_app.logger.error(f"Error checking YouTube API key: {str(e)}")
        flash(f"Unexpected error: {str(e)}", "error")
    
    return redirect(url_for('dashboard.index'))
