# app/extensions.py
"""
This file imports and re-exports extensions for easier importing in other modules.
"""

from app import mongo

# Export the mongo instance for use in other modules, especially serverless functions 