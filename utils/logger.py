import logging
import sys

def setup_logger(name="ERPBot"):
    logger = logging.getLogger(name)
    
    # Prevent duplicate logs if initialized multiple times
    if not logger.handlers:
        logger.setLevel(logging.DEBUG) # Catch everything from DEBUG and up
        
        # Console Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        
        # Format: [2026-07-11 14:00:00] - INFO - ERPBot: Message here
        formatter = logging.Formatter(
            fmt='[%(asctime)s] - %(levelname)s - %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
    return logger

# Export a ready-to-use instance
app_logger = setup_logger()