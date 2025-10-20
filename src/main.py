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
import shutil
from dotenv import load_dotenv
load_dotenv()

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

@app.route('/download/processed/<filename>')
def download_processed_image(filename):
    """Download processed SAR image with proper filename"""
    try:
        # Create a user-friendly filename
        timestamp = filename.split('_')[0]
        download_name = f"sar_analysis_result_{timestamp}.jpg"
        
        processed_dir = os.path.join(app.static_folder, 'processed')
        return send_from_directory(
            processed_dir, 
            filename, 
            as_attachment=True,
            download_name=download_name
        )
    except Exception as e:
        print(f"Download error: {e}")
        return "File not found", 404
        
@app.route('/static/uploads/<filename>')
def serve_uploaded_image(filename):
    upload_dir = os.path.join(app.static_folder, 'uploads')
    return send_from_directory(upload_dir, filename)



# Global variable to cache working client connection
_active_client = None
_active_service_url = None
_connection_status = "not_initialized"

def initialize_sar_connection():
    """Initialize SAR connection at startup"""
    global _connection_status
    print("🔌 Initializing SAR analysis connection at startup...")
    _connection_status = "initializing"
    
    try:
        client, url = get_sar_client()
        if client and url:
            _connection_status = "connected"
            service_name = "Hugging Face Space" if "huggingface" in url else "Local Gradio Server"
            print(f"✅ SAR connection established: {service_name} ({url})")
        else:
            _connection_status = "failed"
            print("❌ Failed to establish SAR connection at startup")
    except Exception as e:
        _connection_status = "error"
        print(f"⚠️ Error during SAR connection initialization: {e}")

def resize_image_if_needed(image_path, max_size=1024):
    """
    Resize image if it's larger than max_size while maintaining aspect ratio
    Returns the path to the resized image (or original if no resize needed)
    """
    try:
        with Image.open(image_path) as img:
            # Get current dimensions
            width, height = img.size
            
            # Check if resize is needed
            if max(width, height) <= max_size:
                return image_path  # No resize needed
            
            # Calculate new dimensions maintaining aspect ratio
            if width > height:
                new_width = max_size
                new_height = int(height * max_size / width)
            else:
                new_height = max_size
                new_width = int(width * max_size / height)
            
            # Resize the image
            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Save resized image (overwrite original for processing)
            resized_img.save(image_path, quality=85, optimize=True)
            
            print(f"📏 Image resized from {width}x{height} to {new_width}x{new_height}")
            return image_path
            
    except Exception as e:
        print(f"⚠️ Image resize failed: {e}")
        return image_path  # Return original path if resize fails

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
    
    from gradio_client import Client
    huggingface_space_url = os.getenv('HF_SPACE_URL', 'https://huggingface.co/spaces/Faethon88/sar_imaging')
    hf_token = os.getenv('HF_TOKEN')
    default_hf_url = 'https://huggingface.co/spaces/Faethon88/sar_imaging'

    def try_connect(url):
        try:
            client = Client(url, hf_token=hf_token)
            return client, None
        except Exception as e:
            return None, e

    # Warn if token is missing and user likely needs it for a private Space
    if not hf_token:
        print("⚠️ HF_TOKEN not set in environment. If your Hugging Face Space is private, set HF_TOKEN to access it.")

    # First: try the configured HF_SPACE_URL
    for attempt in range(2):
        if attempt > 0:
            print(f"🔄 Retry {attempt + 1}/2 for configured HF_SPACE_URL")
            time.sleep(2)
        else:
            print(f"🔌 Connecting to configured HF_SPACE_URL: {huggingface_space_url}")

        client, err = try_connect(huggingface_space_url)
        if client:
            _active_client = client
            _active_service_url = huggingface_space_url
            print(f"✅ Connected to SAR service ({huggingface_space_url})")
            return client, huggingface_space_url
        else:
            err_msg = str(err)[:200]
            print(f"⏳ Connection attempt failed for {huggingface_space_url}: {err_msg}")

    # If configured URL looks like a local address and it failed, try the official HF URL as fallback
    if ('127.0.0.1' in huggingface_space_url) or ('localhost' in huggingface_space_url) or (huggingface_space_url == default_hf_url):
        # If it was already the default, we've already tried it; otherwise attempt default
        if huggingface_space_url != default_hf_url:
            print("🔄 Configured URL failed — trying official Hugging Face Space URL as fallback...")
            for attempt in range(2):
                if attempt > 0:
                    print(f"🔄 Retry {attempt + 1}/2 for official Hugging Face Space")
                    time.sleep(2)
                client, err = try_connect(default_hf_url)
                if client:
                    _active_client = client
                    _active_service_url = default_hf_url
                    print(f"✅ Connected to official Hugging Face Space ({default_hf_url})")
                    return client, default_hf_url
                else:
                    print(f"⏳ Official HF attempt failed: {str(err)[:200]}")

    print("❌ All SAR service connection attempts failed.")
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

        # Resize image if needed (max 1024px)
        temp_path = resize_image_if_needed(temp_path, max_size=1024)

        # Create URL for the uploaded image
        uploaded_image_url = url_for('serve_uploaded_image', filename=filename)

        print(f"Processing SAR image: {filename}")

        # Get SAR analysis client with automatic connection management
        try:
            client, space_url = get_sar_client()

            if not client:
                return jsonify({
                    'error': 'SAR analysis service unavailable',
                    'details': 'Could not connect to Hugging Face Space or local Gradio server. Please check your HF Space status and token.'
                }), 503

            # Read the file content as bytes and build a base64 data URI (JSON-serializable)
            with open(temp_path, 'rb') as f:
                file_bytes = f.read()

            b64 = base64.b64encode(file_bytes).decode('utf-8')
            data_uri = f"data:image/jpeg;base64,{b64}"

            # Build an Image dict that Gradio expects: provide a 'url' (data URI) and metadata
            image_data_obj = {
                "path": None,
                "url": data_uri,
                "size": len(file_bytes),
                "orig_name": filename,
                "mime_type": "image/jpeg",
                "is_stream": False,
                "meta": {}
            }

            # Try uploading the file via gradio_client if supported and include that reference as a fallback.
            uploaded_ref = None
            try:
                # Some gradio_client versions provide upload_file which returns a server-side reference
                if hasattr(client, 'upload_file'):
                    try:
                        uploaded_ref = client.upload_file(temp_path)
                        print(f"🔼 Uploaded file to Gradio host, reference: {uploaded_ref}")
                    except Exception as e:
                        print(f"⚠️ upload_file failed: {e}")
                # Newer versions may expose upload_files or other helpers; ignore if not present
            except Exception as e:
                print(f"⚠️ Error attempting to upload file to gradio host: {e}")

            # Try multiple JSON-serializable payload formats for gradio_client.predict.
            # Order: direct Image dict (preferred), dict with named field, list wrapper, uploaded_ref (if any), path fallbacks.
            predict_attempts = [
                (lambda: client.predict(image_data_obj, api_name="/predict")),
                (lambda: client.predict({"image": image_data_obj}, api_name="/predict")),
                (lambda: client.predict([image_data_obj], api_name="/predict")),
                # If upload returned a host reference, try using it directly
                (lambda: client.predict(uploaded_ref, api_name="/predict") if uploaded_ref else (_ for _ in ()).throw(Exception('no upload_ref'))),
                (lambda: client.predict({"path": temp_path}, api_name="/predict")),
                (lambda: client.predict(temp_path, api_name="/predict"))
            ]

            resp = None
            last_error = None
            for attempt_fn in predict_attempts:
                try:
                    resp = attempt_fn()
                    break
                except Exception as e:
                    last_error = e
                    print(f"⏳ Predict attempt failed: {e}")
                    time.sleep(1)

            if resp is None:
                # Try direct HTTP POST to the Space predict API as a last-resort fallback.
                try:
                    hf_token = os.getenv('HF_TOKEN')
                    # Normalize space_url (remove trailing slash) and try multiple likely endpoints
                    base = space_url.rstrip('/')
                    predict_api_urls = [
                        f"{base}/api/predict/0",
                        f"{base}/run/predict",
                        f"{base}/api/predict",
                        f"{base}/api/predict/1",
                    ]
                    post_err = None
                    for api_url in predict_api_urls:
                        try:
                            headers = {'Content-Type': 'application/json'}
                            if hf_token:
                                headers['Authorization'] = f"Bearer {hf_token}"

                            payload = {"data": [data_uri]}
                            print(f"🔁 Trying direct POST to {api_url} with JSON payload (data URI)")
                            r = requests.post(api_url, json=payload, headers=headers, timeout=30)

                            # Log status and body for debugging
                            print(f"HTTP {r.status_code} from {api_url}")
                            body_preview = (r.text[:1000] + '...') if r.text and len(r.text) > 1000 else r.text
                            print(f"Response body preview: {body_preview}")

                            r.raise_for_status()
                            j = r.json()

                            # Gradio typically returns {'data': [...]} where outputs are in j['data']
                            if isinstance(j, dict) and 'data' in j:
                                resp = j['data']
                                print("✅ Direct POST returned data from Space API")
                                break
                            else:
                                # if response is raw string or other structure, use it directly
                                resp = j
                                print("✅ Direct POST returned JSON (non-standard structure)")
                                break
                        except requests.HTTPError as he:
                            post_err = he
                            print(f"⏳ Direct POST to {api_url} returned HTTP error: {he}")
                            # continue to next endpoint
                        except Exception as e:
                            post_err = e
                            print(f"⏳ Direct POST to {api_url} failed: {e}")
                            time.sleep(1)

                    if resp is None:
                        err_msg = str(post_err) if post_err is not None else (str(last_error) if last_error is not None else 'No response from SAR service')
                        print(f"❌ All predict attempts failed: {err_msg}")
                        return jsonify({'error': 'SAR predict failed', 'details': err_msg}), 502
                except Exception as e:
                    err_msg = str(e)
                    print(f"❌ All predict attempts failed and HTTP fallback failed: {err_msg}")
                    return jsonify({'error': 'SAR predict failed', 'details': err_msg}), 502

            # Parse response shapes: list/tuple, dict, string
            annotated_image_candidate = None
            detection_summary = None

            try:
                if isinstance(resp, (list, tuple)):
                    if len(resp) >= 2:
                        annotated_image_candidate = resp[0]
                        detection_summary = resp[1]
                    elif len(resp) == 1:
                        annotated_image_candidate = resp[0]
                elif isinstance(resp, dict):
                    # Common keys
                    annotated_image_candidate = resp.get('annotated_image') or resp.get('image') or resp.get('output') or resp.get('0')
                    detection_summary = resp.get('detection_summary') or resp.get('summary') or resp.get('1') or resp.get('label')
                elif isinstance(resp, str):
                    # Could be summary text or data URI
                    if resp.startswith('data:image'):
                        annotated_image_candidate = resp
                    else:
                        detection_summary = resp
                else:
                    # Unknown type
                    print(f"⚠️ Unrecognized predict response type: {type(resp)}")
            except Exception as e:
                print(f"⚠️ Error parsing predict response: {e}")

            # Normalize detection_summary
            if detection_summary is None:
                # Try to extract summary from annotated candidate if it's a tuple/dict
                detection_summary = ''

            print(f"Analysis complete. Summary: {detection_summary}")

            # Attempt to save annotated image if present (support path, URL, data URI/base64, bytes)
            processed_filename = f"{timestamp}_sar_result.jpg"
            processed_path = os.path.join(app.config['PROCESSED_FOLDER'], processed_filename)
            processed_url = None
            download_url = None

            if annotated_image_candidate:
                try:
                    # If bytes
                    if isinstance(annotated_image_candidate, (bytes, bytearray)):
                        with open(processed_path, 'wb') as f:
                            f.write(annotated_image_candidate)
                        processed_url = url_for('serve_processed_image', filename=processed_filename)
                        download_url = url_for('download_processed_image', filename=processed_filename)

                    # If data URI
                    elif isinstance(annotated_image_candidate, str) and annotated_image_candidate.startswith('data:image'):
                        header, b64 = annotated_image_candidate.split(',', 1)
                        image_bytes = base64.b64decode(b64)
                        with open(processed_path, 'wb') as f:
                            f.write(image_bytes)
                        processed_url = url_for('serve_processed_image', filename=processed_filename)
                        download_url = url_for('download_processed_image', filename=processed_filename)

                    # If URL (http/https)
                    elif isinstance(annotated_image_candidate, str) and (annotated_image_candidate.startswith('http://') or annotated_image_candidate.startswith('https://')):
                        try:
                            r = requests.get(annotated_image_candidate, timeout=15)
                            r.raise_for_status()
                            with open(processed_path, 'wb') as f:
                                f.write(r.content)
                            processed_url = url_for('serve_processed_image', filename=processed_filename)
                            download_url = url_for('download_processed_image', filename=processed_filename)
                        except Exception as e:
                            print(f"⚠️ Failed to download annotated image from URL: {e}")

                    # If server-side path (may be accessible when running locally)
                    elif isinstance(annotated_image_candidate, str) and os.path.exists(annotated_image_candidate):
                        shutil.copy2(annotated_image_candidate, processed_path)
                        resize_image_if_needed(processed_path, max_size=1024)
                        processed_url = url_for('serve_processed_image', filename=processed_filename)
                        download_url = url_for('download_processed_image', filename=processed_filename)

                    else:
                        print(f"⚠️ Annotated image candidate has unsupported type or format: {type(annotated_image_candidate)}")
                except Exception as e:
                    print(f"⚠️ Error saving annotated image: {e}")

            # Return results
            return jsonify({
                'success': True,
                'detection_summary': detection_summary,
                'annotated_image_url': processed_url,
                'uploaded_image_url': uploaded_image_url,
                'download_url': download_url,
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
    # Return a simple HTML page with a link to the Hugging Face Space
    return f'''
    <html>
    <head><title>Check SAR Model on Hugging Face</title></head>
    <body style="font-family:sans-serif; text-align:center; margin-top:50px;">
        <h2>Check the SAR Model Directly on Hugging Face</h2>
        <p>
            <a href="{hf_space_url}" target="_blank" style="font-size:1.5em; color:#1976d2; text-decoration:none;">
                Open Hugging Face Space
            </a>
        </p>
        <p style="margin-top:40px; color:#888;">If the model is not working here, you can test it directly on Hugging Face.</p>
    </body>
    </html>
    '''


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
            'connection_cached': client is not None,
            'initialization_status': _connection_status,
            'auto_connection': True
        })
        
    except ImportError:
        return jsonify({
            'gradio_client_installed': False,
            'error': 'gradio_client not installed',
            'initialization_status': _connection_status
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
    
    # Initialize SAR connection automatically at startup
    print("🚀 Starting SAR Analysis Website...")
    initialize_sar_connection()
    
    print("🌐 Starting Flask server...")
    app.run(host='0.0.0.0', port=5000, debug=True)


@app.route('/hf-status', methods=['GET'])
def hf_status():
    """Return non-sensitive Hugging Face config status: whether HF_TOKEN is set and HF_MODEL name."""
    hf_token_present = bool(os.getenv('HF_TOKEN'))
    hf_model = os.getenv('HF_MODEL') or None
    return jsonify({'hf_token_present': hf_token_present, 'hf_model': hf_model}), 200