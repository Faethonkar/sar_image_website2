#!/usr/bin/env python3
"""
Production startup script for Railway deployment
Uses direct SAR model integration instead of separate Gradio server
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    """Main production startup"""
    print("🌐 SAR Analysis System - Railway Production Mode")
    print("=" * 50)
    
    # Set production environment
    os.environ['FLASK_ENV'] = 'production'
    
    print("🧠 Using Hugging Face Space for SAR analysis (no local Gradio server)")
    
    # Get port from Railway environment or default to 5000
    port = int(os.environ.get('PORT', 5000))
    host = '0.0.0.0'  # Railway requires binding to 0.0.0.0
    
    print(f"🌟 Starting Flask server on {host}:{port}")
    
    # Change to src directory and start Flask with Gunicorn
    os.chdir('src')
    
    # Use Gunicorn for production
    gunicorn_cmd = [
        'gunicorn',
        '--bind', f'{host}:{port}',
        '--workers', '2',
        '--timeout', '120',
        '--keep-alive', '2',
        '--max-requests', '1000',
        '--max-requests-jitter', '50',
        'main:app'
    ]
    
    try:
        subprocess.run(gunicorn_cmd)
    except Exception as e:
        print(f"❌ Gunicorn failed: {e}")
        print("🔄 Falling back to Flask development server")
        # Fallback to development server
        from main import app
        app.run(host=host, port=port, debug=False)

if __name__ == "__main__":
    main()