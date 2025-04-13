from app import create_app, mongo
from app.services.webhook_service import WebhookService
from app.models.webhook import Webhook
from app.models.video import Video
from datetime import datetime
import json
import requests
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = create_app()

def test_webhooks():
    with app.app_context():
        # 1. Check for webhooks
        webhooks = list(mongo.db.webhooks.find({'active': True}))
        if not webhooks:
            logger.error("No active webhooks found in the database!")
            return
        
        logger.info(f"Found {len(webhooks)} active webhook(s)")
        
        # 2. Create test video data
        test_video = {
            'video_id': 'TEST_VIDEO_ID_' + str(int(time.time())),
            'channel_id': 'TEST_CHANNEL_ID',
            'title': 'Test Video ' + datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
            'description': 'This is a test video for webhook debugging',
            'published_at': datetime.utcnow(),
            'thumbnail_url': 'https://via.placeholder.com/480x360.png?text=Test+Thumbnail',
            'detected_at': datetime.utcnow(),
            'notification_count': 0,
            'is_manual_notification': True
        }
        
        # 3. Direct test each webhook without threading
        for webhook in webhooks:
            logger.info(f"Testing webhook URL: {webhook.get('url')}")
            
            # Prepare headers
            headers = {'Content-Type': 'application/json'}
            if webhook.get('headers'):
                headers.update(webhook['headers'])
            
            # Prepare payload
            payload = {
                'video_id': test_video['video_id'],
                'channel_id': test_video['channel_id'],
                'title': test_video['title'],
                'description': test_video['description'],
                'published_at': test_video['published_at'].isoformat() + 'Z',
                'thumbnail_url': test_video['thumbnail_url'],
                'video_url': f"https://www.youtube.com/watch?v={test_video['video_id']}",
                'notification_time': datetime.utcnow().isoformat() + 'Z',
                'is_manual_notification': True,
                'notification_count': test_video['notification_count'],
                'is_test': True,
                'debug_info': "Direct test from webhook_test.py"
            }
            
            # Direct HTTP request (bypassing the service)
            try:
                logger.info(f"Sending direct HTTP POST to {webhook['url']}")
                logger.info(f"Headers: {headers}")
                logger.info(f"Payload: {json.dumps(payload, default=str)}")
                
                response = requests.post(
                    webhook['url'],
                    headers=headers,
                    data=json.dumps(payload, default=str),
                    timeout=30  # Increased timeout for debugging
                )
                
                logger.info(f"Direct HTTP response: {response.status_code} {response.reason}")
                if response.text:
                    logger.info(f"Response body: {response.text[:500]}")  # Truncate if too long
                
                # Log to database
                delivery_log = {
                    'webhook_id': webhook['_id'],
                    'video_id': test_video['video_id'],
                    'timestamp': datetime.utcnow(),
                    'success': response.status_code >= 200 and response.status_code < 300,
                    'response_code': response.status_code,
                    'response_message': response.reason,
                    'video_title': test_video['title'],
                    'video_thumbnail': test_video['thumbnail_url'],
                    'is_test_notification': True,
                    'is_manual_notification': True,
                    'response_body': response.text[:1000] if response.text else None,
                    'request_headers': json.dumps(headers),
                    'request_body': json.dumps(payload, default=str)
                }
                
                mongo.db.webhook_deliveries.insert_one(delivery_log)
                
            except Exception as e:
                logger.error(f"Error sending direct webhook: {str(e)}")
                
                # Log failure
                delivery_log = {
                    'webhook_id': webhook['_id'],
                    'video_id': test_video['video_id'],
                    'timestamp': datetime.utcnow(),
                    'success': False,
                    'response_code': 0,
                    'response_message': str(e),
                    'video_title': test_video['title'],
                    'video_thumbnail': test_video['thumbnail_url'],
                    'is_test_notification': True,
                    'is_manual_notification': True,
                    'request_headers': json.dumps(headers),
                    'request_body': json.dumps(payload, default=str)
                }
                
                mongo.db.webhook_deliveries.insert_one(delivery_log)
            
            # Now test via service
            logger.info(f"Testing via WebhookService.send_notification for {webhook['url']}")
            
            try:
                result = WebhookService.send_notification(webhook, test_video, is_test=True)
                logger.info(f"Service test result: {result}")
            except Exception as e:
                logger.error(f"Error using service to send webhook: {str(e)}")
                
        logger.info("Webhook testing completed")

if __name__ == "__main__":
    test_webhooks() 