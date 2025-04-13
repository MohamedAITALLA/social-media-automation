# app/tasks/monitor_task.py

import threading
import time
import logging
from datetime import datetime, timedelta
from app import mongo, socketio
from app.services.youtube_service import YouTubeService
from app.services.webhook_service import WebhookService
from flask import current_app
import os
import traceback

logger = logging.getLogger(__name__)

class MonitorTask:
    def __init__(self):
        self.running = False
        self.thread = None
        self.app = None
    
    def start(self, app=None):
        """Start the monitoring task"""
        if self.running:
            logger.warning("Monitor task already running")
            return
        
        # Store the app reference for creating context later
        if app:
            self.app = app
        
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop)
        self.thread.daemon = True
        self.thread.start()
        logger.info("Monitor task started")
    
    def stop(self):
        """Stop the monitoring task"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
            self.thread = None
        logger.info("Monitor task stopped")
    
    def restart(self, app=None):
        """Restart the monitoring task"""
        self.stop()
        self.start(app)
        logger.info("Monitor task restarted")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                # Create an application context for this thread
                if self.app:
                    with self.app.app_context():
                        logger.info("Checking channels with application context")
                        
                        # Add a system event to record the current check time
                        current_time = datetime.utcnow()
                        try:
                            if mongo.db is not None:
                                mongo.db.system_events.insert_one({
                                    'level': 'INFO',
                                    'message': 'Automatic channel check initiated',
                                    'timestamp': current_time,
                                    'type': 'CHANNEL_CHECK',
                                    'details': {'automatic': True}
                                })
                                logger.info(f"Starting scheduled check at {current_time}")
                        except Exception as e:
                            logger.error(f"Error adding system event for scheduled check: {str(e)}")
                            
                        # Run the actual channel check
                        self._check_channels()
                        
                        # Get polling interval directly from current app config first, then fall back to environment
                        polling_interval = current_app.config.get('POLLING_INTERVAL')
                        logger.info(f"Got polling interval from app config: {polling_interval}")
                        
                        # Double-check with environment variable as backup
                        env_polling_interval = os.environ.get('POLLING_INTERVAL')
                        if env_polling_interval and env_polling_interval.isdigit():
                            env_interval = int(env_polling_interval)
                            if env_interval != polling_interval:
                                logger.warning(f"Environment polling interval ({env_interval}) differs from app config ({polling_interval})")
                                polling_interval = env_interval  # Prefer environment variable if different
                        
                        if not polling_interval or polling_interval < 60:
                            polling_interval = 3600  # Default to 1 hour if invalid
                            logger.warning(f"Invalid polling interval ({polling_interval}), using default of 3600 seconds")
                            
                        next_check_time = datetime.utcnow() + timedelta(seconds=polling_interval)
                        logger.info(f"Next check in {polling_interval} seconds (at {next_check_time.strftime('%Y-%m-%d %H:%M:%S')})")
                else:
                    logger.error("No Flask app reference available for creating context")
                    self._check_channels()
                    
                    # Get polling interval directly from environment even without app context
                    env_polling_interval = os.environ.get('POLLING_INTERVAL')
                    if env_polling_interval and env_polling_interval.isdigit():
                        polling_interval = int(env_polling_interval)
                    else:
                        polling_interval = 3600  # Default to 1 hour if no app context or env variable
                    
                    next_check_time = datetime.utcnow() + timedelta(seconds=polling_interval)
                    logger.info(f"Next check in {polling_interval} seconds (at {next_check_time.strftime('%Y-%m-%d %H:%M:%S')})")
                
                # Sleep outside the context
                logger.info(f"Monitor thread sleeping for {polling_interval} seconds")
                time.sleep(polling_interval)
                logger.info("Monitor thread woke up, starting next check cycle")
            except Exception as e:
                logger.error(f"Error in monitor loop: {str(e)}")
                traceback.print_exc()
                time.sleep(60)  # Sleep for a minute before retrying
    
    def _check_channels(self):
        """Check all active channels for new videos"""
        if mongo.db is None:
            logger.error("MongoDB connection not available, skipping channel check")
            return
            
        # Get all active channels
        try:
            active_channels = list(mongo.db.channels.find({'active': True}))
            logger.info(f"Found {len(active_channels)} active channels to check")
            
            # Sort channels by last checked time so we prioritize channels that haven't been checked in a while
            # This helps distribute the API quota more fairly
            active_channels.sort(key=lambda channel: channel.get('last_checked', datetime(1970, 1, 1)))
            
            # Calculate quota limits - don't check all channels every time
            # YouTube API has a daily quota limit, so we need to be careful
            daily_quota_target = 10000  # Standard free quota
            # Estimated units per channel check (search API costs 100 units)
            estimated_units_per_check = 100
            
            # Calculate max channels we should check in one cycle to stay within quota
            cycles_per_day = 86400 / current_app.config.get('POLLING_INTERVAL', 3600)
            max_channels_per_cycle = int(daily_quota_target / (cycles_per_day * estimated_units_per_check))
            
            # Limit the number of channels we check in one go
            if len(active_channels) > max_channels_per_cycle:
                logger.info(f"Limiting channel checks to {max_channels_per_cycle} out of {len(active_channels)} to conserve API quota")
                channels_to_check = active_channels[:max_channels_per_cycle]
            else:
                channels_to_check = active_channels
            
            for channel in channels_to_check:
                try:
                    logger.info(f"Checking channel: {channel.get('channel_name', 'Unknown')} ({channel['channel_id']})")
                    
                    # Check for new videos
                    new_videos = YouTubeService.check_channel_for_new_videos(channel['channel_id'])
                    
                    if new_videos:
                        logger.info(f"Found {len(new_videos)} new videos for channel {channel.get('channel_name', 'Unknown')}")
                        
                        # Process each new video
                        for video in new_videos:
                            # Emit socket event for real-time updates
                            try:
                                socketio.emit('new_video', {
                                    'video_id': video['video_id'],
                                    'channel_id': video['channel_id'],
                                    'title': video['title'],
                                    'thumbnail_url': video['thumbnail_url'],
                                    'channel_name': channel.get('channel_name', 'Unknown')
                                })
                            except Exception as e:
                                logger.error(f"Error emitting socket event: {str(e)}")
                            
                            # Send webhook notifications
                            try:
                                notification_result = WebhookService.notify_all_webhooks(video, is_manual=False)
                                
                                if notification_result['success_count'] > 0:
                                    logger.info(f"Sent {notification_result['success_count']} webhook notifications for video: {video['title']}")
                                    
                                    if notification_result.get('errors'):
                                        logger.warning(f"Some webhook notifications failed: {', '.join(notification_result['errors'][:3])}")
                                        if len(notification_result['errors']) > 3:
                                            logger.warning(f"...and {len(notification_result['errors']) - 3} more errors")
                                else:
                                    logger.warning(f"Failed to send webhook notifications for video: {video['title']}")
                                    if notification_result.get('errors'):
                                        logger.error(f"Webhook errors: {', '.join(notification_result['errors'][:3])}")
                            except Exception as e:
                                logger.error(f"Error sending webhook notifications: {str(e)}")
                                logger.error(traceback.format_exc())
                    else:
                        logger.info(f"No new videos found for channel {channel.get('channel_name', 'Unknown')}")
                
                except Exception as e:
                    logger.error(f"Error checking channel {channel.get('channel_name', channel.get('channel_id', 'Unknown'))}: {str(e)}")
        except Exception as e:
            logger.error(f"Error retrieving active channels: {str(e)}")

# Create a singleton instance
monitor = MonitorTask()

def setup_monitor(app):
    """Setup the monitoring task for the app"""
    logger.info("Setting up monitor task")
    
    # Store the app reference for creating context
    monitor.app = app
    
    # Start the monitor immediately in all environments
    if not monitor.running:
        logger.info("Starting monitor task immediately")
        monitor.start(app)
        
        # Do an immediate check to ensure it's working
        run_immediate_check(app)
    
    return monitor

def run_immediate_check(app):
    """Run an immediate check for new videos"""
    logger.info("Running immediate check for new videos")
    
    # Create a new thread for immediate check
    def _immediate_check():
        with app.app_context():
            try:
                logger.info("Performing immediate channel check")
                
                # Add a system event to record the current check time
                current_time = datetime.utcnow()
                try:
                    if mongo.db is not None:
                        mongo.db.system_events.insert_one({
                            'level': 'INFO',
                            'message': 'Manual channel check initiated',
                            'timestamp': current_time,
                            'type': 'CHANNEL_CHECK',
                            'details': {'manual': True}
                        })
                        logger.info(f"Added system event for channel check at {current_time}")
                except Exception as e:
                    logger.error(f"Error adding system event: {str(e)}")
                
                # Run the actual check
                monitor._check_channels()
                logger.info("Immediate check completed")
            except Exception as e:
                logger.error(f"Error in immediate check: {str(e)}")
    
    # Start the immediate check thread
    thread = threading.Thread(target=_immediate_check)
    thread.daemon = True
    thread.start()
