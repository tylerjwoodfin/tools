#!/usr/bin/env python3
"""
Test script for the service check functionality
"""

import sys
import os

# Add the parent directory to the path so we can import the service check
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from service_check import main
    print("Running service check...")
    main()
    print("Service check completed successfully!")
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)
except Exception as e:  # pylint: disable=broad-exception-caught
    print(f"Error running service check: {e}")
    sys.exit(1)
