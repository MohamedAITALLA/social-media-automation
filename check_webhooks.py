from app import create_app, mongo
import json
from bson.json_util import dumps
from bson.objectid import ObjectId
import sys

app = create_app()

with app.app_context():
    print("Checking webhook configuration and deliveries...\n")
    
    # 1. Check if webhook collection exists
    collections = mongo.db.list_collection_names()
    print(f"Collections in database: {collections}")
    
    # 2. Check webhooks
    webhooks = list(mongo.db.webhooks.find())
    print(f"\nFound {len(webhooks)} webhook(s)")
    
    if webhooks:
        for i, webhook in enumerate(webhooks):
            print(f"\nWebhook #{i+1}:")
            print(f"  URL: {webhook.get('url')}")
            print(f"  Active: {webhook.get('active', False)}")
            print(f"  Description: {webhook.get('description', 'No description')}")
            print(f"  Last delivery: {webhook.get('last_delivery', 'Never')}")
            
            # Check custom headers
            headers = webhook.get('headers', {})
            if headers:
                print(f"  Headers: {headers}")
            
            # Check webhook deliveries
            delivery_count = mongo.db.webhook_deliveries.count_documents({'webhook_id': webhook['_id']})
            print(f"  Delivery records: {delivery_count}")
            
            # Get the latest 3 delivery records
            if delivery_count > 0:
                print("\n  Recent delivery attempts:")
                
                recent_deliveries = list(mongo.db.webhook_deliveries.find(
                    {'webhook_id': webhook['_id']}
                ).sort('timestamp', -1).limit(3))
                
                for j, delivery in enumerate(recent_deliveries):
                    print(f"    Attempt #{j+1}:")
                    print(f"      Time: {delivery.get('timestamp')}")
                    print(f"      Success: {delivery.get('success', False)}")
                    print(f"      Code: {delivery.get('response_code')}")
                    print(f"      Message: {delivery.get('response_message')}")
                    print(f"      Is test: {delivery.get('is_test_notification', False)}")
                    print(f"      Is manual: {delivery.get('is_manual_notification', False)}")
                    print(f"      Video: {delivery.get('video_title', 'Unknown')}")

    else:
        print("\nNo webhooks found in the database!")
        
    # 3. Check if any webhook delivery records exist (even if no webhooks)
    delivery_count = mongo.db.webhook_deliveries.count_documents({})
    print(f"\nTotal webhook delivery records: {delivery_count}")
    
    # 4. Check most recent delivery regardless of webhook
    if delivery_count > 0:
        print("\nMost recent webhook delivery attempts (any webhook):")
        recent_deliveries = list(mongo.db.webhook_deliveries.find().sort('timestamp', -1).limit(3))
        
        for j, delivery in enumerate(recent_deliveries):
            print(f"  Attempt #{j+1}:")
            try:
                webhook_id = delivery.get('webhook_id')
                webhook = mongo.db.webhooks.find_one({'_id': webhook_id})
                webhook_url = webhook.get('url', 'Unknown URL') if webhook else 'Unknown webhook'
            except:
                webhook_url = 'Error getting webhook URL'
                
            print(f"    Webhook: {webhook_url}")
            print(f"    Time: {delivery.get('timestamp')}")
            print(f"    Success: {delivery.get('success', False)}")
            print(f"    Code: {delivery.get('response_code')}")
            print(f"    Message: {delivery.get('response_message')}")
            print(f"    Is test: {delivery.get('is_test_notification', False)}")
            print(f"    Is manual: {delivery.get('is_manual_notification', False)}")
            print(f"    Video: {delivery.get('video_title', 'Unknown')}") 