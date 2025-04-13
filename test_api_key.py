import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# First try getting the API key directly from environment
env_api_key = os.environ.get('YOUTUBE_API_KEY')

if env_api_key:
    # Mask the API key for display
    masked_key = env_api_key[:6] + '*****' + env_api_key[-4:] if len(env_api_key) > 10 else '******'
    print(f"Found API key in environment: {masked_key}")
    api_key = env_api_key
else:
    print("No API key found in environment variables, checking app config...")
    
    # Try getting it from app config as backup
    try:
        from app import create_app
        app = create_app()
        
        with app.app_context():
            api_key = app.config.get('YOUTUBE_API_KEY')
            
            if api_key:
                masked_key = api_key[:6] + '*****' + api_key[-4:] if len(api_key) > 10 else '******'
                print(f"Found API key in app config: {masked_key}")
            else:
                print("ERROR: No YouTube API key found in app configuration")
                exit(1)
    except Exception as e:
        print(f"Error getting API key from app config: {str(e)}")
        if not env_api_key:
            print("No API key available to test")
            exit(1)

# Test URL that uses minimal quota
test_url = f"https://www.googleapis.com/youtube/v3/videos?part=id&chart=mostPopular&maxResults=1&key={api_key}"

try:
    print("\nMaking test request to YouTube API...")
    response = requests.get(test_url)
    
    print(f"Response status code: {response.status_code}")
    
    if response.status_code == 200:
        print("SUCCESS: API key is valid and working correctly")
        data = response.json()
        video_count = len(data.get('items', []))
        print(f"Received {video_count} video(s) in response")
        print("API quota is available")
        
        # Print a sample of the response
        if video_count > 0:
            video_id = data['items'][0]['id']
            print(f"Sample video ID: {video_id}")
            print(f"Video URL: https://www.youtube.com/watch?v={video_id}")
    elif response.status_code == 403:
        error_data = response.json()
        error_reason = error_data.get('error', {}).get('errors', [{}])[0].get('reason', '')
        
        if error_reason == 'quotaExceeded':
            print("ERROR: API key is valid but quota has been exceeded")
            print("Wait until tomorrow for quota to reset or increase your quota limit in Google Cloud Console")
        elif error_reason == 'keyInvalid':
            print("ERROR: API key is invalid or has been revoked")
            print("Check your API key in the Google Cloud Console")
        else:
            print(f"ERROR: API returned 403 error with reason: {error_reason}")
            print(f"Error message: {error_data.get('error', {}).get('message', 'Unknown error')}")
    else:
        print(f"ERROR: Unexpected response code: {response.status_code}")
        print(f"Response: {response.text[:500]}")
except requests.exceptions.RequestException as e:
    print(f"ERROR: Connection error: {str(e)}")
except Exception as e:
    print(f"ERROR: Unexpected error: {str(e)}") 