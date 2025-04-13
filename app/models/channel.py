# app/models/channel.py
from datetime import datetime
from app import mongo
import logging

logger = logging.getLogger(__name__)

class Channel:
    @staticmethod
    def create(channel_id, channel_name):
        if mongo.db is None:
            logger.error("MongoDB connection is not available")
            return None
            
        channel = {
            'channel_id': channel_id,
            'channel_name': channel_name,
            'last_checked': None,
            'active': True,
            'added_at': datetime.utcnow()
        }
        try:
            mongo.db.channels.insert_one(channel)
            return channel
        except Exception as e:
            logger.error(f"Error creating channel: {str(e)}")
            return None
    
    @staticmethod
    def get_all():
        if mongo.db is None:
            logger.error("MongoDB connection is not available")
            return []
            
        try:
            return list(mongo.db.channels.find())
        except Exception as e:
            logger.error(f"Error getting all channels: {str(e)}")
            return []
    
    @staticmethod
    def get_by_id(channel_id):
        if mongo.db is None:
            logger.error("MongoDB connection is not available")
            return None
            
        try:
            return mongo.db.channels.find_one({'channel_id': channel_id})
        except Exception as e:
            logger.error(f"Error getting channel by ID: {str(e)}")
            return None
    
    @staticmethod
    def update_last_checked(channel_id):
        if mongo.db is None:
            logger.error("MongoDB connection is not available")
            return False
            
        try:
            result = mongo.db.channels.update_one(
                {'channel_id': channel_id},
                {'$set': {'last_checked': datetime.utcnow()}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating last checked: {str(e)}")
            return False
    
    @staticmethod
    def toggle_active(channel_id, active_status):
        if mongo.db is None:
            logger.error("MongoDB connection is not available")
            return False
            
        try:
            result = mongo.db.channels.update_one(
                {'channel_id': channel_id},
                {'$set': {'active': active_status}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error toggling active status: {str(e)}")
            return False
    
    @staticmethod
    def delete(channel_id):
        if mongo.db is None:
            logger.error("MongoDB connection is not available")
            return False
            
        try:
            result = mongo.db.channels.delete_one({'channel_id': channel_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting channel: {str(e)}")
            return False
