# check_mongo.py
from flask import Flask
from flask_pymongo import PyMongo
from dotenv import load_dotenv
import os
import sys

# Load environment variables
load_dotenv()

# Create a test Flask app
app = Flask(__name__)

# Get MongoDB URI from environment variables
mongo_uri = os.environ.get('MONGO_URI')
if not mongo_uri:
    print("ERROR: MONGO_URI environment variable is not set!")
    sys.exit(1)

# Set up MongoDB connection
app.config['MONGO_URI'] = mongo_uri
mongo = PyMongo(app)

# Test the connection
try:
    # Force a connection to verify it works
    db_names = mongo.cx.list_database_names()
    print(f"SUCCESS: Connected to MongoDB server")
    print(f"Available databases: {', '.join(db_names)}")
    
    # Get the current database name
    db_name = mongo_uri.split('/')[-1].split('?')[0]
    print(f"Current database: {db_name}")
    
    # List collections in the database
    collections = mongo.db.list_collection_names()
    print(f"Collections in database: {', '.join(collections) if collections else 'None'}")
    
    # Print some stats about each collection
    for collection in collections:
        count = mongo.db[collection].count_documents({})
        print(f"  - {collection}: {count} documents")
    
    print("\nMongoDB connection is working correctly!")
except Exception as e:
    print(f"ERROR: Failed to connect to MongoDB: {str(e)}")
    sys.exit(1) 