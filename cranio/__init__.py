import sys
import logging

# Global logging configuration
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Logging to sys.stdout
h1 = logging.StreamHandler(stream=sys.stdout)   # writes logs to sys.stdout
formatter = logging.Formatter('%(asctime)s.%(msecs)03d;%(threadName)s;%(levelname)s;%(message)s', '%Y-%m-%d %H:%M:%S')
h1.setFormatter(formatter)
logger.addHandler(h1)