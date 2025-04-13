# check_mongo_direct.py
from pymongo import MongoClient
from dotenv import load_dotenv
import os
import sys

# Load environment variables
load_dotenv()

# Get MongoDB URI from environment variables
mongo_uri = os.environ.get('MONGO_URI')
if not mongo_uri:
    print("ERROR: MONGO_URI environment variable is not set!")
    sys.exit(1)

print(f"MongoDB URI: {mongo_uri.replace(mongo_uri.split('@')[0], '***')}")

try:
    # Connect directly to MongoDB
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    
    # Force a server check
    server_info = client.server_info()
    print(f"SUCCESS: Connected to MongoDB server version {server_info.get('version')}")
    
    # List databases
    db_names = client.list_database_names()
    print(f"Available databases: {', '.join(db_names)}")
    
    # Get the current database name
    db_name = mongo_uri.split('/')[-1].split('?')[0]
    print(f"Current database: {db_name}")
    
    # Get the database
    db = client[db_name]
    
    # List collections
    collections = db.list_collection_names()
    print(f"Collections in database: {', '.join(collections) if collections else 'None'}")
    
    # Print some stats about each collection
    for collection in collections:
        count = db[collection].count_documents({})
        print(f"  - {collection}: {count} documents")
    
    print("\nMongoDB connection is working correctly!")
    
except Exception as e:
    print(f"ERROR: Failed to connect to MongoDB: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1) 