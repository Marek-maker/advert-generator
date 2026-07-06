"""
PythonAnywhere WSGI entry point.
Copy this to your PA account: /var/www/{username}_pythonanywhere_com_wsgi.py
Then reload.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import app as application
