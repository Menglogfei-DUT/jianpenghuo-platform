# -*- coding: utf-8 -*-
"""
WSGI entrypoint for platform hosts such as PythonAnywhere.

Point the host's WSGI configuration to this file; it exposes the
WSGI callable named ``application`` which wraps the Flask ``app``.
"""
import os
import sys

# Production default: suppress demo SMS-code echo. Local `python app.py` does not
# go through this entrypoint and keeps the demo behaviour.
os.environ.setdefault('SMS_DEMO', '0')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app as application  # noqa: E402
