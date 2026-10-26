# -*- coding: utf-8 -*-
"""
WSGI entrypoint for platform hosts such as PythonAnywhere.

Point the host's WSGI configuration to this file; it exposes the
WSGI callable named ``application`` which wraps the Flask ``app``.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app as application  # noqa: E402
