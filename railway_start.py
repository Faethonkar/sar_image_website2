#!/usr/bin/env python3
"""
Production startup script for Railway deployment
Uses direct SAR model integration instead of separate Gradio server
"""

import os
import sys
import subprocess
from pathlib import Path
from subprocess import CalledProcessError
import platform

def main():
    """Main production startup"""
    print("🌐 SAR Analysis System - Railway Production Mode")
    print("=" * 50)
    
    # Set production environment
    os.environ['FLASK_ENV'] = 'production'
    
    print("🧠 Using Hugging Face Space for SAR analysis (no local Gradio server)")
    
    # Get port from Railway environment or default to 5000
    port = int(os.environ.get('PORT', os.environ.get('GUNICORN_PORT', 5000)))
    host = os.environ.get('HOST', '0.0.0.0')  # Railway requires binding to 0.0.0.0
    
    print(f"🌟 Starting Flask server on {host}:{port}")
    
    # Change to src directory (where main:app lives) and start Flask with Gunicorn
    src_dir = os.path.join(os.getcwd(), 'src')
    if os.path.isdir(src_dir):
        os.chdir(src_dir)
        # Ensure the src directory is on sys.path so imports like 'from main import app' succeed
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)

    # If running on Windows, prefer waitress (gunicorn is not supported on Windows)
    if platform.system().lower().startswith('win'):
        try:
            from waitress import serve
            print("▶ Detected Windows platform — using waitress WSGI server for local testing")
            # Import app and serve
            from main import app
            serve(app, host=host, port=port)
            return
        except ImportError:
            print("⚠️ Waitress not installed. Falling back to Flask development server for local testing.")
            try:
                from main import app
                app.run(host=host, port=port, debug=False)
                return
            except Exception as ex:
                print(f"⚠️ Fallback Flask server failed on Windows: {ex}")
                # continue to try gunicorn path for completeness

    # Determine worker count: prefer WEB_CONCURRENCY, otherwise use a conservative formula
    try:
        workers = int(os.environ.get('WEB_CONCURRENCY', max(2, (os.cpu_count() or 2) * 2 + 1)))
    except Exception:
        workers = 2

    # Use Gunicorn via the current Python interpreter to ensure the module is found in venv
    gunicorn_cmd = [
        sys.executable, '-m', 'gunicorn',
        '--bind', f'{host}:{port}',
        '--workers', str(workers),
        '--timeout', '120',
        '--keep-alive', '2',
        '--max-requests', '1000',
        '--max-requests-jitter', '50',
        'main:app'
    ]

    try:
        print(f"▶ Running: {' '.join(gunicorn_cmd)}")
        # Run and raise on non-zero exit so we can fallback
        subprocess.run(gunicorn_cmd, check=True)
    except CalledProcessError as e:
        print(f"❌ Gunicorn exited with error code {e.returncode}: {e}")
        print("🔄 Falling back to Flask development server")
        # Fallback to development server (last resort)
        try:
            # Import here to avoid importing Flask app before adjusting PYTHONPATH/CWD
            from main import app
            app.run(host=host, port=port, debug=False)
        except Exception as ex:
            print(f"⚠️ Fallback server failed: {ex}")
            raise

if __name__ == "__main__":
    main()