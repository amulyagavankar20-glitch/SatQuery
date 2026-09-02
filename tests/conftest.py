"""
Pytest configuration — ensures the project root is on sys.path so that
'backend' can be imported without installing the package.
"""
import sys
import os

# Project root is one directory above 'tests/'
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
