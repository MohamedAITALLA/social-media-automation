# test_connection.py
import os
import requests
from dotenv import load_dotenv
from pymongo import MongoClient
import sys

# Load environment variables
load_dotenv()

def test_mongo_connection():
    """Test connection to MongoDB"""
    mongo_uri = os.environ.get('MONGO_URI')
    if not mongo_uri:
        print("ERROR: MONGO_URI environment variable is not set.")
        return False
    
    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        # Force connection to verify it works
        client.server_info()
        db_name = mongo_uri.split('/')[-1].split('?')[0]
        print(f"SUCCESS: Connected to MongoDB database: {db_name}")
        
        # Print some basic stats if possible
        db = client[db_name]
        collections = db.list_collection_names()
        print(f"Collections in database: {', '.join(collections) if collections else 'None'}")
        
        for collection in collections:
            count = db[collection].count_documents({})
            print(f"  - {collection}: {count} documents")
        
        return True
    except Exception as e:
        print(f"ERROR: Failed to connect to MongoDB: {str(e)}")
        return False

def test_youtube_api():
    """Test YouTube API connection"""
    api_key = os.environ.get('YOUTUBE_API_KEY')
    if not api_key:
        print("ERROR: YOUTUBE_API_KEY environment variable is not set.")
        return False
    
    try:
        # Make a simple API request to test the key (using a known video ID)
        response = requests.get(
            f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id=dQw4w9WgXcQ&key={api_key}"
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'items' in data and len(data['items']) > 0:
                video_title = data['items'][0]['snippet']['title']
                print(f"SUCCESS: YouTube API key is valid. Test video title: '{video_title}'")
                return True
            else:
                print("WARNING: YouTube API key seems valid but no data returned for test video.")
                return True
        else:
            print(f"ERROR: YouTube API request failed with status code {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"ERROR: Failed to connect to YouTube API: {str(e)}")
        return False

if __name__ == "__main__":
    print("Testing YouTube Monitor connections...\n")
    
    mongo_success = test_mongo_connection()
    print()  # Empty line for readability
    
    youtube_success = test_youtube_api()
    print()  # Empty line for readability
    
    # Summary
    print("Connection Test Summary:")
    print(f"MongoDB Connection: {'✓ SUCCESS' if mongo_success else '✗ FAILED'}")
    print(f"YouTube API: {'✓ SUCCESS' if youtube_success else '✗ FAILED'}")
    
    # Exit with success or failure code
    if mongo_success and youtube_success:
        print("\nAll connections successful!")
        sys.exit(0)
    else:
        print("\nSome connections failed. Please check the error messages above.")
        sys.exit(1) 