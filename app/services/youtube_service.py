# app/services/youtube_service.py

import requests
import logging
import re
from datetime import datetime
from app.models.video import Video
from app.models.channel import Channel
from app import mongo
from flask import current_app
import os

logger = logging.getLogger(__name__)

class YouTubeService:
    @staticmethod
    def get_channel_info(channel_input):
        """
        Fetch channel information from YouTube API
        Handles different input formats: channel ID, channel username, or full URL
        """
        api_key = current_app.config.get('YOUTUBE_API_KEY')
        if not api_key:
            logger.error("YouTube API key is not set")
            return None
        
        # Extract channel ID from input if it's a URL
        channel_id = YouTubeService._extract_channel_id(channel_input)
        if not channel_id:
            channel_id = channel_input  # Use input as is if not a URL
        
        logger.info(f"Looking up channel with ID: {channel_id}")
        
        # Try looking up by ID first
        channel_info = YouTubeService._get_channel_by_id(channel_id, api_key)
        
        # If not found, try looking up by username
        if not channel_info and len(channel_id) < 24:  # Channel IDs are typically 24 chars
            logger.info(f"Channel not found by ID, trying as username: {channel_id}")
            channel_info = YouTubeService._get_channel_by_username(channel_id, api_key)
        
        return channel_info
    
    @staticmethod
    def _extract_channel_id(input_string):
        """Extract channel ID from a YouTube URL"""
        # Match various YouTube channel URL formats
        channel_patterns = [
            r'youtube\.com/channel/(UC[\w-]+)',  # Standard channel URL
            r'youtube\.com/c/([^/?&]+)',         # Custom URL
            r'youtube\.com/user/([^/?&]+)',      # Username URL
            r'youtube\.com/@([^/?&]+)'           # Handle URL
        ]
        
        for pattern in channel_patterns:
            match = re.search(pattern, input_string)
            if match:
                return match.group(1)
        
        # If it looks like a channel ID already (starts with UC and is ~24 chars)
        if input_string.startswith('UC') and len(input_string) >= 20:
            return input_string
            
        return None
    
    @staticmethod
    def _get_channel_by_id(channel_id, api_key):
        """Get channel info using direct channel ID"""
        url = f"https://www.googleapis.com/youtube/v3/channels?part=snippet&id={channel_id}&key={api_key}"
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            if 'items' not in data or len(data['items']) == 0:
                logger.warning(f"No channel found with ID: {channel_id}")
                return None
            
            channel_info = data['items'][0]
            return {
                'channel_id': channel_id,
                'channel_name': channel_info['snippet']['title'],
                'description': channel_info['snippet'].get('description', ''),
                'thumbnail_url': channel_info['snippet']['thumbnails'].get('default', {}).get('url', '')
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"API request error when fetching channel by ID: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error when fetching channel by ID: {str(e)}")
            return None
    
    @staticmethod
    def _get_channel_by_username(username, api_key):
        """Get channel info using username/handle"""
        url = f"https://www.googleapis.com/youtube/v3/channels?part=snippet&forUsername={username}&key={api_key}"
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            if 'items' not in data or len(data['items']) == 0:
                logger.warning(f"No channel found with username: {username}")
                return None
            
            channel_info = data['items'][0]
            return {
                'channel_id': channel_info['id'],
                'channel_name': channel_info['snippet']['title'],
                'description': channel_info['snippet'].get('description', ''),
                'thumbnail_url': channel_info['snippet']['thumbnails'].get('default', {}).get('url', '')
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"API request error when fetching channel by username: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error when fetching channel by username: {str(e)}")
            return None

    @staticmethod
    def get_latest_videos(channel_id, max_results=5):
        """
        Fetch the latest videos from a channel
        """
        # Try to get API key from app config first
        try:
            api_key = current_app.config.get('YOUTUBE_API_KEY')
            logger.info(f"Using API key from current_app.config: {'Available' if api_key else 'Not available'}")
        except RuntimeError:
            # We might be outside of app context
            api_key = None
        
        # If not available in app config, try environment variables
        if not api_key:
            api_key = os.environ.get('YOUTUBE_API_KEY')
            logger.info(f"Using API key from os.environ: {'Available' if api_key else 'Not available'}")
        
        if not api_key:
            logger.error("YouTube API key is not set in either app config or environment variables")
            return []
        
        logger.info(f"Fetching latest videos for channel {channel_id}, max_results={max_results}")
        
        # The search endpoint is used to find videos by channel
        search_url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&channelId={channel_id}&maxResults={max_results}&order=date&type=video&key={api_key}"
        logger.debug(f"Making API request to: {search_url.replace(api_key, 'API_KEY_HIDDEN')}")
        
        try:
            response = requests.get(search_url)
            
            # Handle specific error cases with more descriptive messages
            if response.status_code == 400:
                try:
                    error_data = response.json()
                    error_message = error_data.get('error', {}).get('message', 'Unknown error')
                    error_reason = error_data.get('error', {}).get('errors', [{}])[0].get('reason', 'unknown')
                    
                    logger.error(f"YouTube API Bad Request error: {error_message}. Reason: {error_reason}")
                    
                    # Try alternative approach - use channels endpoint to get uploads playlist
                    logger.info(f"Trying alternative method to fetch videos for channel {channel_id}")
                    return YouTubeService._get_videos_from_uploads_playlist(channel_id, max_results, api_key)
                except Exception as e:
                    logger.error(f"Error parsing 400 response: {str(e)}")
                    return []
            
            elif response.status_code == 403:
                error_data = response.json()
                error_reason = error_data.get('error', {}).get('errors', [{}])[0].get('reason', 'unknown')
                
                if error_reason == 'quotaExceeded':
                    logger.error("YouTube API quota has been exceeded. Please wait until tomorrow or upgrade your Google Cloud project.")
                elif error_reason == 'keyInvalid':
                    logger.error("The YouTube API key is invalid. Please check your key and make sure it's correctly configured.")
                else:
                    logger.error(f"YouTube API returned 403 Forbidden error. Reason: {error_reason}")
                return []
            
            response.raise_for_status()
            data = response.json()
            
            videos = []
            if 'items' in data:
                logger.info(f"Found {len(data['items'])} video items in API response")
                
                for item in data['items']:
                    try:
                        video_id = item['id']['videoId']
                        
                        published_at = datetime.strptime(item['snippet']['publishedAt'], "%Y-%m-%dT%H:%M:%SZ")
                        
                        # Get a higher quality thumbnail if available
                        thumbnail_url = None
                        thumbnails = item['snippet'].get('thumbnails', {})
                        
                        # Try to get the best quality thumbnail available
                        for quality in ['maxres', 'high', 'medium', 'default']:
                            if quality in thumbnails and 'url' in thumbnails[quality]:
                                thumbnail_url = thumbnails[quality]['url']
                                break
                        
                        if not thumbnail_url and 'default' in thumbnails:
                            thumbnail_url = thumbnails['default'].get('url', '')
                        
                        # Create the video object
                        video = {
                            'video_id': video_id,
                            'channel_id': channel_id,
                            'title': item['snippet']['title'],
                            'description': item['snippet']['description'],
                            'published_at': published_at,
                            'thumbnail_url': thumbnail_url,
                            'detected_at': datetime.utcnow()
                        }
                        videos.append(video)
                        logger.debug(f"Added video to results: {video['title']} ({video_id})")
                    except Exception as e:
                        logger.error(f"Error processing video from API: {str(e)}")
            
            logger.info(f"Returning {len(videos)} videos for channel {channel_id}")
            return videos
        except requests.exceptions.RequestException as e:
            logger.error(f"API request error when fetching videos: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Error fetching videos for channel {channel_id}: {str(e)}")
            return []
    
    @staticmethod
    def _get_videos_from_uploads_playlist(channel_id, max_results=5, api_key=None):
        """
        Alternative method to get videos using the channel's uploads playlist
        """
        if not api_key:
            try:
                api_key = current_app.config.get('YOUTUBE_API_KEY')
                logger.info(f"Using API key from current_app.config: {'Available' if api_key else 'Not available'}")
            except RuntimeError:
                # We might be outside of app context
                api_key = os.environ.get('YOUTUBE_API_KEY')
                logger.info(f"Using API key from os.environ: {'Available' if api_key else 'Not available'}")
            
            if not api_key:
                logger.error("YouTube API key is not set in either app config or environment variables")
                return []
        
        try:
            # Step 1: Get the uploads playlist ID for the channel
            channels_url = f"https://www.googleapis.com/youtube/v3/channels?part=contentDetails&id={channel_id}&key={api_key}"
            logger.debug(f"Making API request to: {channels_url.replace(api_key, 'API_KEY_HIDDEN')}")
            
            response = requests.get(channels_url)
            if response.status_code != 200:
                logger.error(f"API request failed with status code {response.status_code}")
                if response.status_code == 403:
                    error_data = response.json()
                    error_reason = error_data.get('error', {}).get('errors', [{}])[0].get('reason', 'unknown')
                    logger.error(f"API returned 403 error. Reason: {error_reason}")
                return []
                
            response.raise_for_status()
            
            data = response.json()
            if 'items' not in data or len(data['items']) == 0:
                logger.warning(f"No channel found with ID: {channel_id}")
                return []
            
            # Get the uploads playlist ID
            uploads_playlist_id = data['items'][0]['contentDetails']['relatedPlaylists']['uploads']
            logger.info(f"Found uploads playlist ID for channel {channel_id}: {uploads_playlist_id}")
            
            # Step 2: Get videos from the uploads playlist
            playlist_url = f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&maxResults={max_results}&playlistId={uploads_playlist_id}&key={api_key}"
            logger.debug(f"Making API request to: {playlist_url.replace(api_key, 'API_KEY_HIDDEN')}")
            
            response = requests.get(playlist_url)
            if response.status_code != 200:
                logger.error(f"Playlist API request failed with status code {response.status_code}")
                return []
                
            response.raise_for_status()
            
            data = response.json()
            videos = []
            
            if 'items' in data:
                logger.info(f"Found {len(data['items'])} videos in uploads playlist")
                
                for item in data['items']:
                    try:
                        snippet = item['snippet']
                        video_id = snippet['resourceId']['videoId']
                        published_at = datetime.strptime(snippet['publishedAt'], "%Y-%m-%dT%H:%M:%SZ")
                        
                        # Get thumbnail
                        thumbnail_url = None
                        thumbnails = snippet.get('thumbnails', {})
                        
                        for quality in ['maxres', 'high', 'standard', 'medium', 'default']:
                            if quality in thumbnails and 'url' in thumbnails[quality]:
                                thumbnail_url = thumbnails[quality]['url']
                                break
                        
                        if not thumbnail_url and 'default' in thumbnails:
                            thumbnail_url = thumbnails['default'].get('url', '')
                        
                        # Create video object
                        video = {
                            'video_id': video_id,
                            'channel_id': channel_id,
                            'title': snippet['title'],
                            'description': snippet.get('description', ''),
                            'published_at': published_at,
                            'thumbnail_url': thumbnail_url,
                            'detected_at': datetime.utcnow()
                        }
                        
                        videos.append(video)
                        logger.debug(f"Added video to results from uploads playlist: {video['title']} ({video_id})")
                    except Exception as e:
                        logger.error(f"Error processing video from uploads playlist: {str(e)}")
            
            logger.info(f"Returning {len(videos)} videos from uploads playlist for channel {channel_id}")
            return videos
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API request error when fetching uploads playlist: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Error fetching videos from uploads playlist for channel {channel_id}: {str(e)}")
            return []
    
    @staticmethod
    def get_video_details(video_id):
        """
        Fetch detailed information about a specific video
        """
        api_key = current_app.config['YOUTUBE_API_KEY']
        url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,contentDetails,statistics&id={video_id}&key={api_key}"
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            if 'items' not in data or len(data['items']) == 0:
                return None
            
            video_info = data['items'][0]
            snippet = video_info['snippet']
            content_details = video_info['contentDetails']
            statistics = video_info['statistics']
            
            published_at = datetime.strptime(snippet['publishedAt'], "%Y-%m-%dT%H:%M:%SZ")
            
            return {
                'video_id': video_id,
                'channel_id': snippet['channelId'],
                'title': snippet['title'],
                'description': snippet['description'],
                'published_at': published_at,
                'thumbnail_url': snippet['thumbnails'].get('high', {}).get('url', ''),
                'duration': content_details['duration'],
                'view_count': int(statistics.get('viewCount', 0)),
                'like_count': int(statistics.get('likeCount', 0)),
                'comment_count': int(statistics.get('commentCount', 0))
            }
        except Exception as e:
            logger.error(f"Error fetching video details for {video_id}: {str(e)}")
            return None
    
    @staticmethod
    def check_channel_for_new_videos(channel_id):
        """
        Check a channel for new videos and return any found
        """
        logger.info(f"Checking channel {channel_id} for new videos")
        
        try:
            # Update the channel's last checked timestamp IMMEDIATELY
            # This ensures we always update the timestamp, even if we encounter errors later
            current_time = datetime.utcnow()
            if mongo.db is not None:
                try:
                    update_result = mongo.db.channels.update_one(
                        {'channel_id': channel_id},
                        {'$set': {'last_checked': current_time}}
                    )
                    if update_result.modified_count > 0:
                        logger.info(f"Updated last_checked timestamp for channel {channel_id} to {current_time}")
                    else:
                        logger.warning(f"Failed to update last_checked timestamp for channel {channel_id}")
                except Exception as e:
                    logger.error(f"Error updating last_checked timestamp: {str(e)}")
            
            # First check when the last successful check was
            channel = None
            if mongo.db is not None:
                channel = mongo.db.channels.find_one({'channel_id': channel_id})
            
            # Get the latest videos from the API (increased to 15 to get more videos initially)
            logger.debug(f"Fetching latest videos for channel {channel_id}")
            
            # Try to get the API key directly from environment since we're having issues with current_app
            api_key = os.environ.get('YOUTUBE_API_KEY')
            logger.info(f"Using API key from environment: {'Available' if api_key else 'Not available'}")
            
            if not api_key:
                try:
                    api_key = current_app.config.get('YOUTUBE_API_KEY')
                    logger.info(f"Using API key from config: {'Available' if api_key else 'Not available'}")
                except Exception as e:
                    logger.error(f"Error getting API key from config: {str(e)}")
            
            if not api_key:
                logger.error("YouTube API key is not available from any source")
                return []
            
            # Try uploads playlist method first (uses less quota and more reliable)
            try:
                logger.info(f"Using uploads playlist method for channel {channel_id}")
                latest_videos = YouTubeService._get_videos_from_uploads_playlist(channel_id, max_results=15, api_key=api_key)
                
                # If that fails, fall back to the search API
                if not latest_videos:
                    logger.info(f"Uploads playlist method returned no videos, falling back to search API for channel {channel_id}")
                    latest_videos = YouTubeService.get_latest_videos(channel_id, max_results=15)
            except Exception as e:
                logger.error(f"Error fetching videos with uploads playlist method: {str(e)}")
                try:
                    # Fallback to the search API method
                    logger.info(f"Falling back to search API for channel {channel_id}")
                    latest_videos = YouTubeService.get_latest_videos(channel_id, max_results=15)
                except Exception as inner_e:
                    logger.error(f"Error fetching videos with fallback method: {str(inner_e)}")
                    latest_videos = []
            
            if not latest_videos:
                logger.info(f"No videos found for channel {channel_id}")
                return []
            
            logger.info(f"Retrieved {len(latest_videos)} videos from API for channel {channel_id}")
            
            # Check if mongo.db is available
            if mongo.db is None:
                logger.error("MongoDB connection is not available")
                return latest_videos  # Return videos anyway even if we can't save them
            
            # Store new videos in the database
            new_videos = []
            for video in latest_videos:
                try:
                    video_id = video.get('video_id')
                    if not video_id:
                        logger.warning(f"Video missing video_id, skipping: {video}")
                        continue
                        
                    # Check if video already exists
                    existing = mongo.db.videos.find_one({'video_id': video_id})
                    if existing:
                        logger.debug(f"Video {video_id} already exists in database, skipping")
                        continue
                        
                    # This is a new video
                    logger.info(f"Found new video: {video['title']} ({video_id})")
                    
                    # Add notification tracking fields to the video
                    video['notification_sent'] = False
                    video['notification_count'] = 0
                    video['last_notification_time'] = None
                    
                    # Try to insert the video in the database
                    insert_result = mongo.db.videos.insert_one(video)
                    if insert_result.inserted_id:
                        logger.info(f"✓ Successfully added video {video_id} to database")
                        new_videos.append(video)
                        logger.info(f"→ This video will trigger webhook notifications: {video['title']}")
                    else:
                        logger.warning(f"Failed to insert video {video_id} into database")
                except Exception as e:
                    logger.error(f"Error processing video {video.get('video_id', 'unknown')}: {str(e)}")
            
            if new_videos:
                logger.info(f"Found {len(new_videos)} new videos for channel {channel_id} that will trigger notifications")
            else:
                logger.info(f"No new videos found for channel {channel_id} that require notifications")
                
            return new_videos
        except Exception as e:
            logger.error(f"Error checking channel {channel_id} for new videos: {str(e)}")
            return []
    
    @staticmethod
    def batch_import_channels(channel_ids):
        """
        Import multiple channels at once
        Returns a dictionary with success and failure counts
        """
        results = {
            'success': 0,
            'failed': 0,
            'existing': 0,
            'channels': []
        }
        
        for channel_id in channel_ids:
            channel_id = channel_id.strip()
            if not channel_id:
                continue
                
            # Check if channel already exists
            existing = mongo.db.channels.find_one({'channel_id': channel_id})
            if existing:
                results['existing'] += 1
                results['channels'].append({
                    'channel_id': channel_id,
                    'status': 'existing',
                    'name': existing.get('channel_name', 'Unknown')
                })
                continue
            
            # Get channel info from YouTube API
            channel_info = YouTubeService.get_channel_info(channel_id)
            if not channel_info:
                results['failed'] += 1
                results['channels'].append({
                    'channel_id': channel_id,
                    'status': 'failed',
                    'name': None
                })
                continue
            
            # Create new channel
            channel = {
                'channel_id': channel_id,
                'channel_name': channel_info['channel_name'],
                'active': True,
                'added_at': datetime.utcnow(),
                'last_checked': None
            }
            
            mongo.db.channels.insert_one(channel)
            results['success'] += 1
            results['channels'].append({
                'channel_id': channel_id,
                'status': 'success',
                'name': channel_info['channel_name']
            })
        
        return results
