# app/routes/channels.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from app.models.channel import Channel
from app.models.video import Video
from app.services.youtube_service import YouTubeService
import logging
import traceback
from datetime import datetime, timedelta
import os

logger = logging.getLogger(__name__)
channels_bp = Blueprint('channels', __name__)

@channels_bp.route('/')
def index():
    try:
        channels = Channel.get_all() or []
        return render_template('channels.html', channels=channels)
    except Exception as e:
        current_app.logger.error(f"Error in channels index route: {str(e)}")
        flash('An error occurred while fetching the channels', 'error')
        return render_template('channels.html', channels=[])

@channels_bp.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        channel_input = request.form.get('channel_id', '').strip()
        
        # Validate input
        if not channel_input:
            flash('Channel ID or URL is required', 'error')
            return redirect(url_for('channels.add'))
        
        logger.info(f"Attempting to add channel: {channel_input}")
        
        # Check if channel already exists (try to extract ID first)
        extracted_id = YouTubeService._extract_channel_id(channel_input)
        channel_id_to_check = extracted_id if extracted_id else channel_input
        
        if channel_id_to_check.startswith('UC') and Channel.get_by_id(channel_id_to_check):
            flash('Channel already exists in the database', 'error')
            return redirect(url_for('channels.index'))
        
        # Get channel info from YouTube
        channel_info = YouTubeService.get_channel_info(channel_input)
        
        if not channel_info:
            # Provide helpful error message
            if '/' in channel_input or '@' in channel_input:
                flash('Could not find channel with that URL. Make sure it\'s a valid YouTube channel URL.', 'error')
            elif channel_input.startswith('UC'):
                flash('Could not find channel with that ID. Make sure the channel ID is correct.', 'error')
            else:
                flash('Could not find channel. Try using the full YouTube channel URL instead.', 'error')
                
            logger.warning(f"Failed to find YouTube channel: {channel_input}")
            return redirect(url_for('channels.add'))
        
        # Create channel
        result = Channel.create(channel_info['channel_id'], channel_info['channel_name'])
        if result:
            flash(f'Channel "{channel_info["channel_name"]}" added successfully', 'success')
            logger.info(f"Successfully added channel: {channel_info['channel_name']} ({channel_info['channel_id']})")
        else:
            flash('Error adding channel to database', 'error')
            
        return redirect(url_for('channels.index'))
    
    return render_template('channels_add.html')

@channels_bp.route('/<channel_id>')
def view(channel_id):
    channel = Channel.get_by_id(channel_id)
    if not channel:
        flash('Channel not found', 'error')
        return redirect(url_for('channels.index'))
    
    # First get videos already in database
    videos = Video.get_by_channel(channel_id)
    
    # Always fetch latest videos from YouTube to ensure we have the most current data
    try:
        logger.info(f"Fetching latest videos for channel: {channel.get('channel_name')} ({channel_id})")
        new_videos = YouTubeService.check_channel_for_new_videos(channel_id)
        
        if new_videos:
            flash(f'Found {len(new_videos)} new videos!', 'success')
            logger.info(f"Fetched {len(new_videos)} new videos for channel {channel_id}")
            # Refresh videos after fetching to include the new ones
            videos = Video.get_by_channel(channel_id)
        
        # Update the last checked timestamp
        Channel.update_last_checked(channel_id)
    except Exception as e:
        logger.error(f"Error fetching videos: {str(e)}")
        flash(f"Error fetching latest videos: {str(e)}", 'warning')
    
    # Get the current time for calculating the next check time
    current_time = datetime.now()
    
    # Get the settings
    from app.config import config
    active_config = config.get(os.environ.get('FLASK_ENV', 'default'))
    
    # Create settings object similar to what dashboard uses
    settings = {
        'polling_interval': active_config.POLLING_INTERVAL
    }
    
    return render_template('channels_view.html', 
                           channel=channel, 
                           videos=videos, 
                           now=current_time, 
                           settings=settings,
                           timedelta=timedelta)

@channels_bp.route('/<channel_id>/toggle', methods=['POST'])
def toggle(channel_id):
    """Toggle channel active status"""
    try:
        channel = Channel.get_by_id(channel_id)
        if not channel:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': 'Channel not found'}), 404
            else:
                flash('Channel not found', 'error')
                return redirect(url_for('channels.index'))
        
        # Get current status and toggle it
        current_status = channel.get('active', True)
        new_status = not current_status
        
        # Update in database
        success = Channel.toggle_active(channel_id, new_status)
        
        # Log the action
        logger.info(f"Toggled channel {channel_id} from {'active' if current_status else 'inactive'} to {'active' if new_status else 'inactive'}")
        
        # Check if this is an AJAX request
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        if is_ajax:
            # AJAX response
            if success:
                return jsonify({
                    'success': True,
                    'active': new_status,
                    'message': f"Channel {'activated' if new_status else 'paused'} successfully"
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to update channel status in database'
                })
        else:
            # Regular form submission (non-AJAX)
            if success:
                flash(f"Channel {'activated' if new_status else 'paused'} successfully", 'success')
            else:
                flash("Failed to update channel status", 'error')
            return redirect(url_for('channels.view', channel_id=channel_id))
            
    except Exception as e:
        logger.error(f"Error toggling channel status: {str(e)}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': f"An error occurred: {str(e)}"}), 500
        else:
            flash(f"An error occurred: {str(e)}", 'error')
            return redirect(url_for('channels.view', channel_id=channel_id))

@channels_bp.route('/<channel_id>/delete', methods=['POST'])
def delete(channel_id):
    channel = Channel.get_by_id(channel_id)
    if not channel:
        flash('Channel not found', 'error')
        return redirect(url_for('channels.index'))
    
    Channel.delete(channel_id)
    flash('Channel deleted successfully', 'success')
    return redirect(url_for('channels.index'))

@channels_bp.route('/batch', methods=['POST'])
def batch_import():
    if 'file' not in request.files:
        flash('No file provided', 'error')
        return redirect(url_for('channels.index'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('channels.index'))
    
    # Process CSV file with channel IDs
    try:
        content = file.read().decode('utf-8')
        channel_ids = [line.strip() for line in content.split('\n') if line.strip()]
        
        added = 0
        skipped = 0
        
        for channel_id in channel_ids:
            # Skip if already exists
            if Channel.get_by_id(channel_id):
                skipped += 1
                continue
            
            # Get channel info
            channel_info = YouTubeService.get_channel_info(channel_id)
            if channel_info:
                Channel.create(channel_id, channel_info['title'])
                added += 1
            else:
                skipped += 1
        
        flash(f'Imported {added} channels, skipped {skipped}', 'success')
    except Exception as e:
        flash(f'Error importing channels: {str(e)}', 'error')
    
    return redirect(url_for('channels.index'))

@channels_bp.route('/import', methods=['GET', 'POST'])
def import_channels():
    if request.method == 'POST':
        channel_ids = request.form.get('channel_ids', '').split('\n')
        
        if not channel_ids:
            flash('Please enter at least one channel ID', 'error')
            return redirect(url_for('channels.import_channels'))
        
        # Process the channel IDs
        results = YouTubeService.batch_import_channels(channel_ids)
        
        if results['success'] > 0:
            flash(f"Successfully imported {results['success']} channels", 'success')
        
        if results['existing'] > 0:
            flash(f"{results['existing']} channels were already in the database", 'info')
        
        if results['failed'] > 0:
            flash(f"Failed to import {results['failed']} channels", 'error')
        
        return render_template('channels_import_results.html', results=results)
    
    return render_template('channels_import.html')

@channels_bp.route('/<channel_id>/fetch_videos', methods=['POST'])
def fetch_videos(channel_id):
    """Manually fetch videos for a channel"""
    channel = Channel.get_by_id(channel_id)
    if not channel:
        flash('Channel not found', 'error')
        return redirect(url_for('channels.index'))
    
    try:
        # Use the YouTube API to fetch videos with a higher limit
        logger.info(f"Fetching all available videos for channel {channel_id}")
        latest_videos = YouTubeService.get_latest_videos(channel_id, max_results=50)
        
        # If the normal method fails, try the alternative method
        if not latest_videos:
            logger.info(f"Trying alternative method to fetch videos for channel {channel_id}")
            latest_videos = YouTubeService._get_videos_from_uploads_playlist(channel_id, max_results=50)
        
        if latest_videos:
            # Process new videos
            new_count = 0
            for video in latest_videos:
                video_id = video.get('video_id')
                # Check if video already exists in database
                if not Video.exists(video_id):
                    # Add notification tracking fields to the video
                    video['notification_sent'] = False
                    video['notification_count'] = 0
                    video['last_notification_time'] = None
                    video['detected_at'] = datetime.utcnow()
                    
                    # Insert the video
                    try:
                        mongo.db.videos.insert_one(video)
                        new_count += 1
                        logger.info(f"✓ Successfully added video {video_id} to database: {video['title']}")
                        
                        # Also notify webhooks about this new video
                        try:
                            from app.services.webhook_service import WebhookService
                            logger.info(f"→ Sending webhook notifications for video: {video['title']}")
                            notification_result = WebhookService.notify_all_webhooks(video, is_manual=True)
                            
                            if notification_result['success_count'] > 0:
                                logger.info(f"Sent {notification_result['success_count']} webhook notifications for video: {video['title']}")
                                
                                if notification_result.get('errors'):
                                    logger.warning(f"Some webhook notifications failed: {', '.join(notification_result['errors'][:3])}")
                            else:
                                logger.warning(f"Failed to send webhook notifications for video: {video['title']}")
                                if notification_result.get('errors'):
                                    logger.error(f"Webhook errors: {', '.join(notification_result['errors'][:3])}")
                        except Exception as e:
                            logger.error(f"Error sending webhook notifications: {str(e)}")
                            logger.error(traceback.format_exc())
                            
                    except Exception as e:
                        logger.error(f"Error inserting video {video_id}: {str(e)}")
                        
            if new_count:
                flash(f'Successfully fetched {new_count} new videos! Webhook notifications have been sent.', 'success')
                logger.info(f"Manually fetched {new_count} videos for channel {channel_id}")
            else:
                flash('No new videos found', 'info')
                logger.info(f"No new videos found for channel {channel_id}")
        else:
            flash('No videos found for this channel', 'warning')
            logger.warning(f"No videos found for channel {channel_id}")
            
        # Update the last checked timestamp
        current_time = datetime.utcnow()
        try:
            update_result = mongo.db.channels.update_one(
                {'channel_id': channel_id},
                {'$set': {'last_checked': current_time}}
            )
            
            if update_result.modified_count > 0:
                logger.info(f"Updated last_checked timestamp for channel {channel_id} to {current_time}")
            else:
                logger.warning(f"Failed to update last_checked timestamp for channel {channel_id}")
                
            # Also add a system event for this check
            if mongo.db is not None:
                mongo.db.system_events.insert_one({
                    'level': 'INFO',
                    'message': f'Manual fetch videos for channel {channel["channel_name"]}',
                    'timestamp': current_time,
                    'type': 'CHANNEL_CHECK',
                    'details': {'manual': True, 'channel_id': channel_id}
                })
                logger.info(f"Added system event for manual channel check at {current_time}")
        except Exception as e:
            logger.error(f"Error updating last_checked timestamp: {str(e)}")
            
        Channel.update_last_checked(channel_id)
    except Exception as e:
        logger.error(f"Error fetching videos: {str(e)}")
        logger.error(traceback.format_exc())
        flash(f'Error fetching videos: {str(e)}', 'error')
    
    return redirect(url_for('channels.view', channel_id=channel_id))

@channels_bp.route('/<channel_id>/video/<video_id>/notify', methods=['POST'])
def send_manual_notification(channel_id, video_id):
    """Manually send a notification for a specific video"""
    channel = Channel.get_by_id(channel_id)
    if not channel:
        flash('Channel not found', 'error')
        return redirect(url_for('channels.index'))
    
    # Check if video exists
    video = Video.get_by_id(video_id)
    if not video:
        flash('Video not found', 'error')
        return redirect(url_for('channels.view', channel_id=channel_id))
    
    try:
        from app import mongo
        from app.services.webhook_service import WebhookService
        import traceback
        
        # Get current notification count before sending
        notification_count = Video.get_notification_count(video_id)
        
        # Update video with current count for webhook payload
        video_with_count = dict(video)
        video_with_count['notification_count'] = notification_count
        video_with_count['is_manual_notification'] = True
        
        # Log message about attempting to send notification
        logger.info(f"Sending manual notification for video: {video['title']} ({video_id})")
        
        # Get all active webhooks (similar to test notification logic)
        active_webhooks = list(mongo.db.webhooks.find({'active': True}))
        webhook_count = len(active_webhooks)
        
        if webhook_count == 0:
            logger.warning("No active webhooks found when attempting to send manual notification")
            flash('No active webhooks configured. Please add and activate webhooks first.', 'warning')
            return redirect(url_for('channels.view', channel_id=channel_id))
        
        logger.info(f"Found {webhook_count} active webhooks to notify")
        success_count = 0
        errors = []
        
        # Process each webhook directly (no threading) for better error reporting
        for webhook in active_webhooks:
            try:
                logger.info(f"Sending notification to webhook: {webhook.get('url')}")
                
                # Send notification directly (not in thread)
                result = WebhookService.send_notification(webhook, video_with_count, is_test=False)
                
                if result['success']:
                    logger.info(f"Successfully sent notification to {webhook.get('url')}")
                    success_count += 1
                else:
                    error_msg = f"Failed to send notification to {webhook.get('url')}: {result.get('message')}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    
            except Exception as webhook_error:
                error_msg = f"Error sending to webhook {webhook.get('url')}: {str(webhook_error)}"
                logger.error(error_msg)
                logger.error(traceback.format_exc())
                errors.append(error_msg)
        
        # Mark the notification as sent and increment count regardless of partial failures
        Video.mark_notification_sent(video_id)
        
        # Get updated notification count
        new_notification_count = notification_count + 1
        
        # Log the results
        logger.info(f"Manual notification complete. Success: {success_count}/{webhook_count}")
        
        # Show appropriate message based on results
        if success_count == webhook_count:
            flash(f'Notification successfully sent to all {webhook_count} webhooks for video: {video["title"]}. Total notifications for this video: {new_notification_count}', 'success')
        elif success_count > 0:
            flash(f'Notification sent to {success_count} out of {webhook_count} webhooks with some errors. Total notifications for this video: {new_notification_count}', 'warning')
        else:
            error_summary = '; '.join(errors[:2]) + ('; and more errors' if len(errors) > 2 else '')
            flash(f'Failed to send notifications to any webhooks. Errors: {error_summary}', 'error')
    
    except Exception as e:
        logger.error(f"Error in send_manual_notification: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        flash(f'Error sending notification: {str(e)}', 'error')
    
    return redirect(url_for('channels.view', channel_id=channel_id))
