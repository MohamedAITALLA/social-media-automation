# app/models/system_event.py

from datetime import datetime, timedelta
from app import mongo
from bson.objectid import ObjectId
import logging

logger = logging.getLogger(__name__)

class SystemEvent:
    LEVELS = {
        'info': 'bg-blue-100 text-blue-800',
        'warning': 'bg-yellow-100 text-yellow-800',
        'error': 'bg-red-100 text-red-800',
        'success': 'bg-green-100 text-green-800'
    }
    
    @staticmethod
    def add_event(message, level='info'):
        """Add a new system event"""
        if mongo.db is None:
            logger.error(f"MongoDB connection is not available. Could not log event: {message}")
            return None
            
        event = {
            'message': message,
            'level': level,
            'timestamp': datetime.utcnow()
        }
        
        try:
            mongo.db.system_events.insert_one(event)
            return event
        except Exception as e:
            logger.error(f"Error adding system event: {str(e)}")
            return None
    
    @staticmethod
    def get_recent_events(limit=10):
        """Get recent system events"""
        if mongo.db is None:
            logger.error("MongoDB connection is not available")
            return []
            
        try:
            events = list(mongo.db.system_events.find().sort('timestamp', -1).limit(limit))
            
            # Add CSS classes for styling
            for event in events:
                event['level_class'] = SystemEvent.LEVELS.get(event['level'], SystemEvent.LEVELS['info'])
            
            return events
        except Exception as e:
            logger.error(f"Error getting recent events: {str(e)}")
            return []
    
    @staticmethod
    def clear_old_events(days=30):
        """Clear events older than the specified number of days"""
        if mongo.db is None:
            logger.error("MongoDB connection is not available")
            return 0
            
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            result = mongo.db.system_events.delete_many({'timestamp': {'$lt': cutoff}})
            return result.deleted_count
        except Exception as e:
            logger.error(f"Error clearing old events: {str(e)}")
            return 0
