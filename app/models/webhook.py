# app/models/webhook.py
from datetime import datetime
from app import mongo
from bson.objectid import ObjectId
import logging

logger = logging.getLogger(__name__)

class Webhook:
    @staticmethod
    def create(url, description="", headers=None, active=True):
        if mongo.db is None:
            logger.error("MongoDB connection is not available")
            return None
            
        webhook = {
            'url': url,
            'description': description,
            'headers': headers or {},
            'active': active,
            'created_at': datetime.utcnow()
        }
        try:
            result = mongo.db.webhooks.insert_one(webhook)
            webhook['_id'] = result.inserted_id
            return webhook
        except Exception as e:
            logger.error(f"Error creating webhook: {str(e)}")
            return None
    
    @staticmethod
    def get_all():
        if mongo.db is None:
            logger.error("MongoDB connection is not available")
            return []
            
        try:
            return list(mongo.db.webhooks.find())
        except Exception as e:
            logger.error(f"Error getting all webhooks: {str(e)}")
            return []
    
    @staticmethod
    def get_by_id(webhook_id):
        if mongo.db is None:
            logger.error("MongoDB connection is not available")
            return None
            
        try:
            if isinstance(webhook_id, str):
                webhook_id = ObjectId(webhook_id)
            return mongo.db.webhooks.find_one({'_id': webhook_id})
        except Exception as e:
            logger.error(f"Error getting webhook by ID: {str(e)}")
            return None
    
    @staticmethod
    def get_active():
        if mongo.db is None:
            logger.error("MongoDB connection is not available")
            return []
            
        try:
            return list(mongo.db.webhooks.find({'active': True}))
        except Exception as e:
            logger.error(f"Error getting active webhooks: {str(e)}")
            return []
    
    @staticmethod
    def update(webhook_id, url=None, description=None, headers=None, active=None):
        if mongo.db is None:
            logger.error("MongoDB connection is not available")
            return False
            
        try:
            if isinstance(webhook_id, str):
                webhook_id = ObjectId(webhook_id)
            
            update_data = {}
            if url is not None:
                update_data['url'] = url
            if description is not None:
                update_data['description'] = description
            if headers is not None:
                update_data['headers'] = headers
            if active is not None:
                update_data['active'] = active
            
            if update_data:
                result = mongo.db.webhooks.update_one(
                    {'_id': webhook_id},
                    {'$set': update_data}
                )
                return result.modified_count > 0
            return False
        except Exception as e:
            logger.error(f"Error updating webhook: {str(e)}")
            return False
    
    @staticmethod
    def delete(webhook_id):
        if mongo.db is None:
            logger.error("MongoDB connection is not available")
            return False
            
        try:
            if isinstance(webhook_id, str):
                webhook_id = ObjectId(webhook_id)
            result = mongo.db.webhooks.delete_one({'_id': webhook_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Error deleting webhook: {str(e)}")
            return False
