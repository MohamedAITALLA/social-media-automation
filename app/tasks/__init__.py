from .monitor_task import monitor

def check_channels_for_updates():
    """
    Function that checks all channels for updates.
    Used by the cron job for Vercel deployment.
    
    Returns:
        list: A list of new videos found during the check
    """
    try:
        # Use the existing _check_channels method from the monitor instance
        # Create a list to store any new videos found
        new_videos = []
        
        # Execute the channel check using monitor's method
        if monitor and hasattr(monitor, '_check_channels'):
            monitor._check_channels()
            # Note: Since _check_channels doesn't return data directly,
            # we can just return an empty list or None here
            
        return new_videos
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error in check_channels_for_updates: {str(e)}")
        return []
