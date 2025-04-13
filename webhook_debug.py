import os
import requests
import json
import logging
from datetime import datetime

# Configure logging to console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_webhook_url(url, headers=None):
    """Test a webhook URL directly without any dependencies on the application"""
    logger.info(f"Starting direct webhook test to URL: {url}")
    
    # Default headers
    default_headers = {'Content-Type': 'application/json'}
    if headers:
        default_headers.update(headers)
    
    # Create test payload
    test_payload = {
        'video_id': 'TEST_ID_' + datetime.utcnow().strftime('%Y%m%d%H%M%S'),
        'channel_id': 'TEST_CHANNEL',
        'title': 'Webhook Debug Test',
        'description': 'This is a direct test from webhook_debug.py',
        'published_at': datetime.utcnow().isoformat() + 'Z',
        'thumbnail_url': 'https://via.placeholder.com/480x360.png?text=Test+Thumbnail',
        'video_url': 'https://www.youtube.com/watch?v=TEST_ID',
        'notification_time': datetime.utcnow().isoformat() + 'Z',
        'is_manual_notification': True,
        'is_test': True,
        'debug_info': 'Direct test from webhook_debug.py'
    }
    
    logger.info(f"Headers: {json.dumps(default_headers)}")
    logger.info(f"Payload: {json.dumps(test_payload, default=str)}")
    
    try:
        # Send the request with extended timeout
        response = requests.post(
            url,
            headers=default_headers,
            data=json.dumps(test_payload, default=str),
            timeout=30  # Extended timeout for debugging
        )
        
        # Log the response
        logger.info(f"Response status: {response.status_code} {response.reason}")
        
        # Log headers
        logger.info(f"Response headers: {dict(response.headers)}")
        
        # Log response body if exists
        if response.text:
            logger.info(f"Response body: {response.text[:1000]}")  # Truncate if too long
        
        return {
            'success': response.status_code >= 200 and response.status_code < 300,
            'status_code': response.status_code,
            'reason': response.reason,
            'body': response.text[:1000] if response.text else None
        }
            
    except requests.exceptions.ConnectionError as ce:
        logger.error(f"Connection error: {str(ce)}")
        return {'success': False, 'error': f"Connection error: {str(ce)}"}
    except requests.exceptions.Timeout as te:
        logger.error(f"Timeout error: {str(te)}")
        return {'success': False, 'error': f"Timeout error: {str(te)}"}
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        return {'success': False, 'error': f"Request error: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {'success': False, 'error': f"Unexpected error: {str(e)}"}

if __name__ == "__main__":
    # Get webhook URL from user
    webhook_url = input("Enter your webhook URL: ")
    
    if not webhook_url:
        logger.error("No webhook URL provided")
        exit(1)
    
    # Check for basic URL validation
    if not webhook_url.startswith(('http://', 'https://')):
        logger.warning("URL does not start with http:// or https://. Prefixing with https://")
        webhook_url = 'https://' + webhook_url
    
    # Ask for custom headers
    use_custom_headers = input("Do you want to add custom headers? (y/n): ").lower() == 'y'
    custom_headers = {}
    
    if use_custom_headers:
        print("Enter headers one by one (format: 'Key: Value'). Empty line to finish.")
        while True:
            header_line = input("> ")
            if not header_line:
                break
                
            try:
                key, value = header_line.split(':', 1)
                custom_headers[key.strip()] = value.strip()
            except ValueError:
                logger.error(f"Invalid header format: {header_line}. Expected format: 'Key: Value'")
    
    # Perform the test
    result = test_webhook_url(webhook_url, custom_headers)
    
    # Print result summary
    print("\n===== TEST RESULTS =====")
    if result.get('success'):
        print(f"SUCCESS: Webhook received status {result.get('status_code')} {result.get('reason')}")
    else:
        print(f"FAILED: {result.get('error') or 'HTTP Error: ' + str(result.get('status_code'))}")
    
    print("\nCheck the logs above for detailed information about the request and response.")
    print("If the request was successful but you still don't see anything on your webhook endpoint,")
    print("check the following:")
    print("1. Your webhook server is properly logging incoming requests")
    print("2. There might be network/firewall restrictions between this server and your webhook endpoint")
    print("3. Your webhook endpoint might have specific payload format requirements")
    print("4. Your webhook might need authentication that wasn't provided in this test") 