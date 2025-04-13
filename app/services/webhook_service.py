# app/services/webhook_service.py

import requests
import json
import logging
from datetime import datetime
from app import mongo
from flask import current_app
from threading import Thread
import time
from bson.objectid import ObjectId
import traceback

logger = logging.getLogger(__name__)

class WebhookService:
    @staticmethod
    def send_notification(webhook, video_data, is_test=False):
        """
        Send a notification to a webhook endpoint
        """
        try:
            # Debug log at start
            logger.info(f"Starting webhook notification to {webhook.get('url')} (Test: {is_test})")
            
            # Check if webhook URL is valid
            webhook_url = webhook.get('url')
            if not webhook_url:
                logger.error("Webhook URL is missing or empty")
                return {
                    'success': False,
                    'status_code': 0,
                    'message': "Webhook URL is missing or empty"
                }
                
            if not webhook_url.startswith(('http://', 'https://')):
                logger.warning(f"Webhook URL doesn't start with http:// or https://: {webhook_url}")
                
            # Prepare headers
            headers = {
                'Content-Type': 'application/json'
            }
            
            # Add custom headers if defined
            if webhook.get('headers'):
                headers.update(webhook['headers'])
            
            # Extract manual notification flag if present
            is_manual = video_data.get('is_manual_notification', False)
            
            # Debug log video data
            logger.debug(f"Video data keys: {video_data.keys()}")
            
            # Check for required fields
            required_fields = ['video_id', 'channel_id', 'title', 'description', 'published_at', 'thumbnail_url']
            missing_fields = [field for field in required_fields if field not in video_data]
            
            if missing_fields:
                logger.warning(f"Missing required fields in video_data: {missing_fields}")
                # Add placeholder values for missing fields to prevent errors
                for field in missing_fields:
                    if field == 'published_at':
                        video_data[field] = datetime.utcnow()
                    elif field == 'thumbnail_url':
                        video_data[field] = 'https://via.placeholder.com/480x360.png?text=Missing+Thumbnail'
                    else:
                        video_data[field] = f"MISSING_{field}"
            
            # Prepare payload
            payload = {
                'video_id': video_data['video_id'],
                'channel_id': video_data['channel_id'],
                'title': video_data['title'],
                'description': video_data['description'],
                'published_at': video_data['published_at'].isoformat() + 'Z',
                'thumbnail_url': video_data['thumbnail_url'],
                'video_url': f"https://www.youtube.com/watch?v={video_data['video_id']}",
                'notification_time': datetime.utcnow().isoformat() + 'Z',
                'is_manual_notification': is_manual
            }
            
            # Add notification count if available
            if 'notification_count' in video_data:
                payload['notification_count'] = video_data['notification_count']
            
            # Add test flag for test notifications
            if is_test:
                payload['is_test'] = True
                
            # Debug log request details
            logger.info(f"Preparing webhook request to {webhook_url}")
            logger.debug(f"Headers: {headers}")
            logger.debug(f"Payload: {json.dumps(payload, default=str)[:500]}")  # Truncate if too large
            
            # Send the request
            response = requests.post(
                webhook_url, 
                headers=headers, 
                data=json.dumps(payload, default=str),
                timeout=10
            )
            
            # Debug log response
            logger.info(f"Webhook response: {response.status_code} {response.reason}")
            
            if response.text:
                logger.debug(f"Response body: {response.text[:500]}") # Truncate if too large
            
            # Log the delivery attempt
            delivery_log = {
                'webhook_id': webhook['_id'],
                'video_id': video_data['video_id'],
                'timestamp': datetime.utcnow(),
                'success': response.status_code >= 200 and response.status_code < 300,
                'response_code': response.status_code,
                'response_message': response.reason,
                'video_title': video_data['title'],
                'video_thumbnail': video_data['thumbnail_url'],
                'is_test_notification': is_test,
                'is_manual_notification': is_manual,
                'request_headers': json.dumps(headers),
                'request_body': json.dumps(payload, default=str)[:1000],
                'response_body': response.text[:1000] if response.text else None
            }
            
            try:
                mongo.db.webhook_deliveries.insert_one(delivery_log)
                logger.debug("Webhook delivery log saved to database")
            except Exception as db_error:
                logger.error(f"Error saving webhook delivery log: {str(db_error)}")
            
            # Update webhook's last delivery timestamp
            try:
                mongo.db.webhooks.update_one(
                    {'_id': webhook['_id']},
                    {'$set': {'last_delivery': datetime.utcnow()}}
                )
                logger.debug("Updated webhook's last_delivery timestamp")
            except Exception as update_error:
                logger.error(f"Error updating webhook last_delivery: {str(update_error)}")
            
            return {
                'success': response.status_code >= 200 and response.status_code < 300,
                'status_code': response.status_code,
                'message': response.reason
            }
        except requests.exceptions.ConnectionError as ce:
            logger.error(f"Connection error sending webhook notification: {str(ce)}")
            return WebhookService._handle_webhook_error(webhook, video_data, is_test, ce, "Connection error")
        except requests.exceptions.Timeout as te:
            logger.error(f"Timeout error sending webhook notification: {str(te)}")
            return WebhookService._handle_webhook_error(webhook, video_data, is_test, te, "Timeout error")
        except requests.exceptions.RequestException as re:
            logger.error(f"Request error sending webhook notification: {str(re)}")
            return WebhookService._handle_webhook_error(webhook, video_data, is_test, re, "Request error")
        except Exception as e:
            logger.error(f"Unexpected error sending webhook notification: {str(e)}")
            logger.error(traceback.format_exc())
            return WebhookService._handle_webhook_error(webhook, video_data, is_test, e, "Unexpected error")
    
    @staticmethod
    def _handle_webhook_error(webhook, video_data, is_test, exception, error_type):
        """Helper method to handle webhook errors consistently"""
        try:
            # Log the failed delivery attempt
            delivery_log = {
                'webhook_id': webhook['_id'],
                'video_id': video_data['video_id'],
                'timestamp': datetime.utcnow(),
                'success': False,
                'response_code': 0,
                'response_message': f"{error_type}: {str(exception)}",
                'video_title': video_data.get('title', 'Unknown'),
                'video_thumbnail': video_data.get('thumbnail_url', 'Unknown'),
                'is_test_notification': is_test,
                'is_manual_notification': video_data.get('is_manual_notification', False),
                'error_details': traceback.format_exc()
            }
            
            mongo.db.webhook_deliveries.insert_one(delivery_log)
        except Exception as log_error:
            logger.error(f"Error logging webhook failure: {str(log_error)}")
            
        return {
            'success': False,
            'status_code': 0,
            'message': f"{error_type}: {str(exception)}"
        }
    
    @staticmethod
    def notify_all_webhooks(video_data, is_manual=False):
        """
        Send notifications to all active webhooks
        
        Args:
            video_data: Dictionary containing video information
            is_manual: Boolean flag indicating if this is a manual notification
        """
        try:
            # Get all active webhooks
            active_webhooks = list(mongo.db.webhooks.find({'active': True}))
            webhook_count = len(active_webhooks)
            
            logger.info(f"Notifying {webhook_count} active webhooks (manual: {is_manual})")
            
            if webhook_count == 0:
                logger.warning("No active webhooks found to notify")
                return {
                    'webhook_count': 0,
                    'success_count': 0,
                    'message': 'No active webhooks found'
                }
            
            success_count = 0
            errors = []
            
            # Process each webhook directly (no threading) for better reliability and error reporting
            for webhook in active_webhooks:
                try:
                    # Log webhook details
                    logger.info(f"Sending notification to webhook: {webhook.get('url')}")
                    
                    # Add manual flag to video data
                    video_data_with_flags = dict(video_data)
                    video_data_with_flags['is_manual_notification'] = is_manual
                    
                    if 'notification_count' in video_data:
                        video_data_with_flags['previous_notification_count'] = video_data['notification_count']
                    
                    # Send notification directly rather than in a thread
                    result = WebhookService.send_notification(webhook, video_data_with_flags)
                    
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
            
            # Log the results
            logger.info(f"Notification complete. Success: {success_count}/{webhook_count}")
            
            # Return comprehensive result
            return {
                'webhook_count': webhook_count,
                'success_count': success_count,
                'errors': errors,
                'all_succeeded': success_count == webhook_count
            }
        except Exception as e:
            logger.error(f"Error in notify_all_webhooks: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                'webhook_count': 0,
                'success_count': 0,
                'errors': [str(e)],
                'all_succeeded': False
            }
    
    @staticmethod
    def _send_with_retry(webhook, video_data):
        """
        Send a webhook notification with retry logic
        """
        max_retries = current_app.config.get('MAX_RETRIES', 3)
        retry_delay = current_app.config.get('RETRY_DELAY', 300)  # seconds
        
        logger.info(f"Starting webhook delivery with retry (max_retries={max_retries}, delay={retry_delay}s)")
        
        for attempt in range(max_retries + 1):
            logger.info(f"Webhook delivery attempt {attempt+1}/{max_retries+1} to {webhook.get('url')}")
            
            result = WebhookService.send_notification(webhook, video_data)
            
            if result['success']:
                logger.info(f"Webhook notification sent successfully to {webhook['url']}")
                return
            
            logger.warning(f"Webhook delivery failed (attempt {attempt+1}/{max_retries+1}): {result['message']}")
            
            # If we've reached max retries, give up
            if attempt >= max_retries:
                logger.error(f"Max retries reached for webhook {webhook['_id']}, giving up")
                return
            
            # Wait before retrying
            logger.info(f"Waiting {retry_delay} seconds before retry...")
            time.sleep(retry_delay)
    
    @staticmethod
    def send_test_notification(webhook_id, custom_message=None):
        """
        Send a test notification to a webhook
        """
        try:
            logger.info(f"Sending test notification to webhook: {webhook_id}")
            
            # Convert string webhook_id to ObjectId if needed
            if isinstance(webhook_id, str):
                webhook_id = ObjectId(webhook_id)
            
            webhook = mongo.db.webhooks.find_one({'_id': webhook_id})
            if not webhook:
                logger.error(f"Webhook not found: {webhook_id}")
                return {
                    'success': False,
                    'message': 'Webhook not found'
                }
            
            logger.info(f"Found webhook: {webhook.get('url')}")
            
            # Create test payload
            test_data = {
                'video_id': 'TEST_VIDEO_ID',
                'channel_id': 'TEST_CHANNEL_ID',
                'title': 'Test Notification',
                'description': custom_message or 'This is a test notification from YouTube Channel Monitor',
                'published_at': datetime.utcnow(),
                'thumbnail_url': 'https://via.placeholder.com/480x360.png?text=Test+Thumbnail',
                'detected_at': datetime.utcnow()
            }
            
            # Send the notification
            logger.info("Sending test notification...")
            result = WebhookService.send_notification(webhook, test_data, is_test=True)
            
            logger.info(f"Test notification result: {result}")
            
            return {
                'success': result['success'],
                'message': f"Test notification {'sent successfully' if result['success'] else 'failed'}: {result['message']}"
            }
        except Exception as e:
            logger.error(f"Error sending test notification: {str(e)}")
            logger.error(traceback.format_exc())
            return {
                'success': False,
                'message': f"Error: {str(e)}"
            }
    
    @staticmethod
    def get_delivery_history(webhook_id, limit=10):
        """
        Get the delivery history for a webhook
        """
        try:
            # Convert string webhook_id to ObjectId if needed
            if isinstance(webhook_id, str):
                webhook_id = ObjectId(webhook_id)
            
            history = list(mongo.db.webhook_deliveries.find(
                {'webhook_id': webhook_id}
            ).sort('timestamp', -1).limit(limit))
            
            return history
        except Exception as e:
            logger.error(f"Error retrieving webhook delivery history: {str(e)}")
            return []
