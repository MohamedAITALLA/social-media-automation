from http.server import BaseHTTPRequestHandler
import sys
import os
import time
import logging
from datetime import datetime

# Add parent directory to path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.tasks import check_channels_for_updates
from app.extensions import mongo

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            start_time = time.time()
            logger.info(f"Cron job started at {datetime.now().isoformat()}")
            
            # Run the channel check task
            updates = check_channels_for_updates()
            
            # Calculate execution time
            execution_time = time.time() - start_time
            
            # Return success response
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            
            response = f"Cron job completed in {execution_time:.2f} seconds. Checked for updates on YouTube channels."
            if updates:
                response += f" Found {len(updates)} new videos."
            
            self.wfile.write(response.encode())
            logger.info(f"Cron job completed in {execution_time:.2f} seconds")
            
        except Exception as e:
            logger.error(f"Error in cron job: {str(e)}")
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Error: {str(e)}".encode()) 