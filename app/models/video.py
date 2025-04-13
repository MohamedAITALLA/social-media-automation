# app/models/video.py
from datetime import datetime
from app import mongo
import logging

logger = logging.getLogger(__name__)

class Video:
    @staticmethod
    def create(video_id, channel_id, title, description, published_at, thumbnail_url):
        if mongo.db is None:
            logger.error("MongoDB connection is not available")
            return None
            
        video = {
            'video_id': video_id,
            'channel_id': channel_id,
            'title': title,
            'description': description,
            'published_at': published_at,
            'thumbnail_url': thumbnail_url,
            'notification_sent': False,
            'notification_count': 0,
            'last_notification_time': None,
            'created_at': datetime.utcnow()
        }
        try:
            mongo.db.videos.insert_one(video)
            return video
        except Exception as e:
            logger.error(f"Error creating video: {str(e)}")
            return None
    
    @staticmethod
    def get_all(limit=50):
        if mongo.db is None:
            logger.error("MongoDB connection is not available")
            return []
            
        try:
            return list(mongo.db.videos.find().sort('published_at', -1).limit(limit))
        except Exception as e:
            logger.error(f"Error getting all videos: {str(e)}")
            return []
    
    @staticmethod
    def get_by_id(video_id):
        if mongo.db is None:
            logger.error("MongoDB connection is not available")
            return None
            
        try:
            return mongo.db.videos.find_one({'video_id': video_id})
        except Exception as e:
            logger.error(f"Error getting video by ID: {str(e)}")
            return None
    
    @staticmethod
    def get_by_channel(channel_id, limit=100):
        if mongo.db is None:
            logger.error("MongoDB connection is not available")
            return []
            
        try:
            return list(mongo.db.videos.find({'channel_id': channel_id}).sort('published_at', -1).limit(limit))
        except Exception as e:
            logger.error(f"Error getting videos by channel: {str(e)}")
            return []
    
    @staticmethod
    def exists(video_id):
        if mongo.db is None:
            logger.error("MongoDB connection is not available")
            return False
            
        try:
            return mongo.db.videos.count_documents({'video_id': video_id}) > 0
        except Exception as e:
            logger.error(f"Error checking if video exists: {str(e)}")
            return False
    
    @staticmethod
    def mark_notification_sent(video_id):
        """Mark a video as having a notification sent and increment counter"""
        if mongo.db is None:
            logger.error("MongoDB connection is not available")
            return False
            
        try:
            current_time = datetime.utcnow()
            result = mongo.db.videos.update_one(
                {'video_id': video_id},
                {'$set': {
                    'notification_sent': True,
                    'last_notification_time': current_time
                },
                 '$inc': {'notification_count': 1}
                }
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error marking notification sent: {str(e)}")
            return False
            
    @staticmethod
    def get_notification_count(video_id):
        """Get the number of times notifications were sent for a video"""
        if mongo.db is None:
            logger.error("MongoDB connection is not available")
            return 0
            
        try:
            video = mongo.db.videos.find_one({'video_id': video_id})
            if video:
                return video.get('notification_count', 0)
            return 0
        except Exception as e:
            logger.error(f"Error getting notification count: {str(e)}")
            return 0
