import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'  # Add this line first
import sys
import json
import time
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import base64
from io import BytesIO
import numpy as np
import torch
import torchvision
import requests  # For Hugging Face API interaction
import certifi

# Ensure requests/ssl use certifi's CA bundle (helps in environments with broken/default certs)
ca_bundle = certifi.where()
os.environ.setdefault('REQUESTS_CA_BUNDLE', ca_bundle)
os.environ.setdefault('SSL_CERT_FILE', ca_bundle)
print(f"Using CA bundle: {ca_bundle}")

# Try to import YOLO - graceful fallback for deployment
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    print("Warning: ultralytics not available. YOLO ship detection will be disabled.")
    YOLO_AVAILABLE = False

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("python-dotenv not installed. Install it with: pip install python-dotenv")
    print("Environment variables will be loaded from system environment only.")


# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, request, jsonify, make_response, url_for, redirect
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# Initialize Flask app
app = Flask(__name__, 
            static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src', 'static'),
            instance_relative_config=True,
            instance_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance'))

# Set the correct static folder path
static_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src', 'static')
app.static_folder = static_folder

# Then create subfolders
for folder in ['uploads', 'processed']:
    os.makedirs(os.path.join(static_folder, folder), exist_ok=True)

# Configuration
basedir = os.path.abspath(os.path.dirname(__file__))
instance_path = os.path.join(basedir, 'instance')

# Ensure the instance directory exists
Path(instance_path).mkdir(parents=True, exist_ok=True)

# JSON file for contact submissions
submissions_file = os.path.join(instance_path, 'contact_submissions.json')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'a_secure_temporary_secret_key')

# Add these with your other configurations
# Change these configurations:
app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'uploads')
app.config['PROCESSED_FOLDER'] = os.path.join(app.static_folder, 'processed')

# Then ensure the directories exist:
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)

# Basic Authentication Setup
auth = HTTPBasicAuth()
admin_username = os.getenv('ADMIN_USERNAME', 'admin')
admin_password = os.getenv('ADMIN_PASSWORD', 'defaultpassword')
users = {
    admin_username: generate_password_hash(admin_password, method='pbkdf2:sha256')
}

@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username

# JSON storage functions
def load_submissions():
    """Load contact submissions from JSON file"""
    try:
        if os.path.exists(submissions_file):
            with open(submissions_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Ensure data is a list
                if isinstance(data, list):
                    return data
                else:
                    print(f"Invalid data format in {submissions_file}, expected list")
                    return []
        return []
    except json.JSONDecodeError as e:
        print(f"JSON decode error loading submissions: {e}")
        return []
    except Exception as e:
        print(f"Error loading submissions: {e}")
        return []

def save_submissions(submissions):
    """Save contact submissions to JSON file"""
    try:
        with open(submissions_file, 'w', encoding='utf-8') as f:
            json.dump(submissions, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving submissions: {e}")
        return False

def add_submission(name, email, message):
    """Add a new contact submission"""
    submissions = load_submissions()
    
    # Check for duplicate email
    for sub in submissions:
        if sub['email'] == email:
            return False, "Email already exists"
    
    # Create new submission
    new_submission = {
        'id': len(submissions) + 1,
        'name': name,
        'email': email,
        'message': message,
        'submitted_at': datetime.now().isoformat(),
        'admin_comment': '',
        'status': 'new'  # new, replied, archived
    }
    
    submissions.append(new_submission)
    
    if save_submissions(submissions):
        return True, "Submission saved successfully"
    else:
        return False, "Error saving submission"

def update_submission_comment(submission_id, comment, status='replied'):
    """Update admin comment and status for a submission"""
    submissions = load_submissions()
    
    for sub in submissions:
        if sub['id'] == submission_id:
            sub['admin_comment'] = comment
            sub['status'] = status
            if save_submissions(submissions):
                return True, "Comment updated successfully"
            else:
                return False, "Error saving comment"
    
    return False, "Submission not found"

def delete_submission(submission_id):
    """Delete a submission by ID"""
    submissions = load_submissions()
    
    # Find and remove the submission
    for i, sub in enumerate(submissions):
        if sub['id'] == submission_id:
            del submissions[i]
            if save_submissions(submissions):
                return True, "Submission deleted successfully"
            else:
                return False, "Error deleting submission"
    
    return False, "Submission not found"

# Route to serve static files
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
        return "Static folder not configured", 404

    # Check if path is a file
    file_path = os.path.join(static_folder_path, path)
    if os.path.isfile(file_path):
        return send_from_directory(static_folder_path, path)
    
    # Check if path is a directory with index.html
    if os.path.isdir(file_path):
        index_path = os.path.join(file_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, os.path.join(path, 'index.html'))
    
    # Check for HTML file with .html extension
    if not path.endswith('.html') and os.path.exists(os.path.join(static_folder_path, path + '.html')):
        return send_from_directory(static_folder_path, path + '.html')
    
    # Default to index.html if nothing else matches
    index_path = os.path.join(static_folder_path, 'index.html')
    if os.path.exists(index_path):
        return send_from_directory(static_folder_path, 'index.html')
    
    return "File not found", 404

# Contact form submission
@app.route('/submit_contact', methods=['POST'])
def handle_contact_form():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')

        if not name or not email or not message:
            return jsonify({'status': 'error', 'message': 'All fields are required.'}), 400

        if '@' not in email or '.' not in email.split('@')[-1]:
            return jsonify({'status': 'error', 'message': 'Invalid email format.'}), 400

        success, msg = add_submission(name, email, message)
        if success:
            return jsonify({'message': 'Form submitted successfully! Your message has been saved and will be reviewed.'})
        else:
            return jsonify({'message': f'Error: {msg}'}), 400

    return jsonify({'status': 'error', 'message': 'Method not allowed'}), 405

# Admin page to view submissions (protected)
@app.route('/admin', methods=['GET'])
@auth.login_required
def admin_page():
    return send_from_directory(app.static_folder, 'admin.html')

# Admin route to view submissions (protected)
@app.route('/admin/submissions', methods=['GET'])
@auth.login_required
def view_submissions():
    try:
        submissions = load_submissions()
        # Sort by submitted_at in descending order (newest first)
        if submissions:
            submissions.sort(key=lambda x: x.get('submitted_at', ''), reverse=True)
        return jsonify(submissions)
    except Exception as e:
        print(f"Error in view_submissions: {e}")
        return jsonify({'error': str(e)}), 500

# Admin route to export submissions as CSV (protected)
@app.route('/admin/export', methods=['GET'])
@auth.login_required
def export_submissions():
    submissions = load_submissions()
    
    # Generate CSV content
    csv_content = "ID,Name,Email,Message,Submitted At,Status,Admin Comment\n"
    for sub in submissions:
        # Escape quotes in message and comment
        message = sub['message'].replace('"', '""')
        comment = sub.get('admin_comment', '').replace('"', '""')
        csv_content += f"{sub['id']},{sub['name']},{sub['email']},\"{message}\",{sub['submitted_at']},{sub.get('status', 'new')},\"{comment}\"\n"
    
    response = make_response(csv_content)
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=submissions.csv'
    return response

# Admin route to update submission comment (protected)
@app.route('/admin/submissions/<int:submission_id>/comment', methods=['POST'])
@auth.login_required
def update_comment(submission_id):
    try:
        data = request.get_json()
        comment = data.get('comment', '')
        status = data.get('status', 'replied')
        
        success, message = update_submission_comment(submission_id, comment, status)
        if success:
            return jsonify({'message': message})
        else:
            return jsonify({'error': message}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Admin route to delete submission (protected)
@app.route('/admin/submissions/<int:submission_id>', methods=['DELETE'])
@auth.login_required
def delete_submission_route(submission_id):
    try:
        success, message = delete_submission(submission_id)
        if success:
            return jsonify({'message': message})
        else:
            return jsonify({'error': message}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/detect_ships', methods=['POST'])
def detect_ships():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    try:
        # Validate file extension
        if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            return jsonify({'error': 'Invalid file type'}), 400

        # Save original upload
        timestamp = int(datetime.now().timestamp())
        upload_filename = secure_filename(f"{timestamp}_{file.filename}")
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], upload_filename)
        file.save(upload_path)

        # Process image
        img = Image.open(upload_path)
        
        if YOLO_AVAILABLE:
            # YOLO processing available
            try:
                model_path = os.path.join(Path(__file__).parent.parent, "src", "models", "yolo", "best.pt")
                if os.path.exists(model_path):
                    model = YOLO(model_path)
                    results = model(img)
                    result = results[0]
                    
                    # Count detections
                    num_ships = len([box for box in result.boxes if box.conf >= 0.3])
                    
                    # Create processed image in memory
                    processed_img = Image.fromarray(result.plot())
                else:
                    # Model file not found
                    num_ships = 0
                    processed_img = img
            except Exception as e:
                print(f"YOLO processing error: {e}")
                num_ships = 0
                processed_img = img
        else:
            # YOLO not available - return original image
            num_ships = 0
            processed_img = img
            
        # Convert to base64 for temporary display
        buffered = BytesIO()
        processed_img.save(buffered, format="JPEG")
        img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        return jsonify({
            'num_ships': num_ships,
            'processed_image': f"data:image/jpeg;base64,{img_str}",
            'uploaded_image': url_for('serve_uploaded_image', filename=upload_filename),
            'message': 'Ship detection unavailable in deployment mode' if not YOLO_AVAILABLE else ('No ships detected' if num_ships == 0 else None)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/save_image', methods=['POST'])
def save_image():
    try:
        if request.headers['Content-Type'] == 'application/json':
            # Handling processed image (JSON)
            data = request.get_json()
            if not data or 'image_data' not in data:
                return jsonify({'error': 'No image data provided'}), 400
            
            # Extract base64 data
            image_data = data['image_data'].split(',')[1]  # Remove data:image/jpeg;base64 prefix
            image_bytes = base64.b64decode(image_data)
            
            # Generate filename
            filename = data.get('filename', f"{int(datetime.now().timestamp())}_detection.jpg")
            filepath = os.path.join(app.config['PROCESSED_FOLDER'], filename)
            
            # Save the processed image
            with open(filepath, 'wb') as f:
                f.write(image_bytes)
            
            return jsonify({
                'message': 'Processed image saved successfully',
                'saved_path': url_for('serve_processed_image', filename=filename)
            })
        else:
            # Handling original image (multipart/form-data)
            if 'file' not in request.files:
                return jsonify({'error': 'No file uploaded'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No selected file'}), 400
            
            # Use provided filename or generate one
            filename = request.form.get('filename', secure_filename(f"{int(datetime.now().timestamp())}_{file.filename}"))
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            # Save the original image
            file.save(filepath)
            
            return jsonify({
                'message': 'Original image saved successfully',
                'saved_path': url_for('serve_uploaded_image', filename=filename)
            })
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    
@app.route('/static/processed/<filename>')
def serve_processed_image(filename):
    processed_dir = os.path.join(app.static_folder, 'processed')
    return send_from_directory(processed_dir, filename)
        
@app.route('/static/uploads/<filename>')
def serve_uploaded_image(filename):
    upload_dir = os.path.join(app.static_folder, 'uploads')
    return send_from_directory(upload_dir, filename)



# Global variable to cache working client connection
_active_client = None
_active_service_url = None

def get_sar_client():
    """Get or establish connection to SAR analysis service"""
    global _active_client, _active_service_url
    
    # If we have an active client, test it first
    if _active_client and _active_service_url:
        try:
            # Quick test to see if the connection is still alive
            print(f"🔄 Testing existing connection to {_active_service_url}")
            return _active_client, _active_service_url
        except Exception:
            print(f"💔 Lost connection to {_active_service_url}, reconnecting...")
            _active_client = None
            _active_service_url = None
    
    # Connection priority: HF Space -> Local Server
    service_configs = [
        {
            'url': 'https://huggingface.co/spaces/Faethon88/sar_imaging',
            'name': 'Hugging Face Space',
            'retries': 2,
            'timeout': 10
        },
        {
            'url': 'http://127.0.0.1:7860',
            'name': 'Local Gradio Server', 
            'retries': 1,
            'timeout': 5
        }
    ]
    
    from gradio_client import Client
    
    for config in service_configs:
        for attempt in range(config['retries']):
            try:
                if attempt > 0:
                    print(f"🔄 Retry {attempt + 1}/{config['retries']} for {config['name']}")
                    time.sleep(3)
                else:
                    print(f"🔌 Connecting to {config['name']}...")
                
                client = Client(config['url'])
                _active_client = client
                _active_service_url = config['url']
                
                print(f"✅ Connected to {config['name']} ({config['url']})")
                return client, config['url']
                
            except Exception as e:
                error_msg = str(e)[:100] + "..." if len(str(e)) > 100 else str(e)
                if attempt < config['retries'] - 1:
                    print(f"⏳ {config['name']} attempt {attempt + 1} failed: {error_msg}")
                else:
                    print(f"❌ {config['name']} unavailable: {error_msg}")
    
    return None, None

# SAR Image Analysis - Send image to Hugging Face Space and return results
@app.route('/analyze-sar', methods=['POST'])
def analyze_sar():
    """
    Receive an uploaded image, send it to the SAR analysis service,
    and return the results back to the client.
    """
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        # Validate file extension
        if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            return jsonify({'error': 'Invalid file type. Please use PNG, JPG, or JPEG.'}), 400

        # Save uploaded file for display (keep original for user to see)
        timestamp = int(datetime.now().timestamp())
        filename = secure_filename(f"{timestamp}_{file.filename}")
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(temp_path)
        
        # Create URL for the uploaded image
        uploaded_image_url = url_for('serve_uploaded_image', filename=filename)

        print(f"Processing SAR image: {filename}")

        # Get SAR analysis client with automatic connection management
        try:
            client, space_url = get_sar_client()
            
            if not client:
                return jsonify({
                    'error': 'SAR analysis service unavailable',
                    'details': 'Could not connect to any analysis service. Please ensure local Gradio server is running.'
                }), 503

            # Send image for analysis using the correct format we discovered
            result = client.predict({"path": temp_path}, api_name="/predict")
            
            if not result or len(result) < 2:
                return jsonify({
                    'error': 'Invalid response from SAR analysis service'
                }), 502

            # Extract results
            annotated_image_path = result[0]  # Path to annotated image
            detection_summary = result[1]     # Text summary
            
            print(f"Analysis complete: {detection_summary}")

            # Copy annotated image to processed folder for serving
            processed_filename = f"{timestamp}_sar_result.jpg"
            processed_path = os.path.join(app.config['PROCESSED_FOLDER'], processed_filename)
            
            if annotated_image_path and os.path.exists(annotated_image_path):
                import shutil
                shutil.copy2(annotated_image_path, processed_path)
                processed_url = url_for('serve_processed_image', filename=processed_filename)
            else:
                processed_url = None

            # Don't clean up the uploaded file - keep it for display
            # The uploaded file will be served via serve_uploaded_image route

            # Return results
            return jsonify({
                'success': True,
                'detection_summary': detection_summary,
                'annotated_image_url': processed_url,
                'uploaded_image_url': uploaded_image_url,
                'original_filename': file.filename,
                'processed_at': datetime.now().isoformat(),
                'space_used': space_url
            })

        except ImportError:
            return jsonify({
                'error': 'SAR analysis service not available',
                'details': 'gradio_client not installed'
            }), 503
            
        except Exception as e:
            print(f"Error during SAR analysis: {e}")
            return jsonify({
                'error': 'SAR analysis failed',
                'details': str(e)
            }), 500

    except Exception as e:
        print(f"Error in analyze_sar: {e}")
        return jsonify({'error': str(e)}), 500


# Simple redirect to open the Hugging Face Space UI in the user's browser  
@app.route('/open-space', methods=['GET'])
def open_space():
    hf_space_url = os.getenv('HF_SPACE_URL', 'https://huggingface.co/spaces/Faethon88/sar_imaging')
    return redirect(hf_space_url, code=302)


# Status endpoint to check SAR analysis service availability
@app.route('/sar-status', methods=['GET'])
def sar_status():
    """Check if SAR analysis services are available."""
    try:
        # Use the auto-connection system to check what's available
        client, active_url = get_sar_client()
        
        services = {
            'huggingface_space': {'url': 'https://huggingface.co/spaces/Faethon88/sar_imaging', 'status': 'unknown'},
            'local_server': {'url': 'http://127.0.0.1:7860', 'status': 'unknown'}
        }
        
        if client and active_url:
            # Mark the active service as available
            if 'huggingface' in active_url:
                services['huggingface_space']['status'] = 'available (active)'
                services['local_server']['status'] = 'not tested (HF working)'
            else:
                services['local_server']['status'] = 'available (active)'
                services['huggingface_space']['status'] = 'unavailable (using local fallback)'
        else:
            # Test each service individually
            from gradio_client import Client
            for service_name, service_info in services.items():
                try:
                    test_client = Client(service_info['url'])
                    service_info['status'] = 'available'
                except Exception as e:
                    service_info['status'] = f'unavailable: {str(e)[:100]}'
        
        return jsonify({
            'gradio_client_installed': True,
            'active_service': active_url,
            'services': services,
            'connection_cached': client is not None
        })
        
    except ImportError:
        return jsonify({
            'gradio_client_installed': False,
            'error': 'gradio_client not installed'
        })

# Auto-connect endpoint to establish connection proactively
@app.route('/sar-connect', methods=['POST'])
def sar_connect():
    """Proactively establish connection to SAR analysis service."""
    try:
        global _active_client, _active_service_url
        # Reset any cached connection to force reconnection
        _active_client = None
        _active_service_url = None
        
        client, service_url = get_sar_client()
        
        if client:
            return jsonify({
                'success': True,
                'connected_to': service_url,
                'message': f'Successfully connected to {"Hugging Face Space" if "huggingface" in service_url else "Local Gradio Server"}'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to connect to any SAR analysis service'
            }), 503
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    # Create the instance directory if it doesn't exist
    if not os.path.exists(os.path.join(basedir, 'instance')):
        os.makedirs(os.path.join(basedir, 'instance'))
    
    app.run(host='0.0.0.0', port=5000, debug=True)


@app.route('/hf-status', methods=['GET'])
def hf_status():
    """Return non-sensitive Hugging Face config status: whether HF_TOKEN is set and HF_MODEL name."""
    hf_token_present = bool(os.getenv('HF_TOKEN'))
    hf_model = os.getenv('HF_MODEL') or None
    return jsonify({'hf_token_present': hf_token_present, 'hf_model': hf_model}), 200