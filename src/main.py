import os
from gradio_client import Client
os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'
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
import requests
import certifi
import shutil
from dotenv import load_dotenv
load_dotenv()

# Ensure requests/ssl use certifi's CA bundle
ca_bundle = certifi.where()
os.environ.setdefault('REQUESTS_CA_BUNDLE', ca_bundle)
os.environ.setdefault('SSL_CERT_FILE', ca_bundle)
print(f"Using CA bundle: {ca_bundle}")

# Try to import YOLO
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    print("Warning: ultralytics not available. YOLO ship detection will be disabled.")
    YOLO_AVAILABLE = False

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("python-dotenv not installed. Environment variables will be loaded from system environment only.")

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

# Upload configurations
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
        'status': 'new'
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
    
    for i, sub in enumerate(submissions):
        if sub['id'] == submission_id:
            del submissions[i]
            if save_submissions(submissions):
                return True, "Submission deleted successfully"
            else:
                return False, "Error deleting submission"
    
    return False, "Submission not found"

# Routes
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
        return "Static folder not configured", 404

    file_path = os.path.join(static_folder_path, path)
    if os.path.isfile(file_path):
        return send_from_directory(static_folder_path, path)
    
    if os.path.isdir(file_path):
        index_path = os.path.join(file_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, os.path.join(path, 'index.html'))
    
    if not path.endswith('.html') and os.path.exists(os.path.join(static_folder_path, path + '.html')):
        return send_from_directory(static_folder_path, path + '.html')
    
    index_path = os.path.join(static_folder_path, 'index.html')
    if os.path.exists(index_path):
        return send_from_directory(static_folder_path, 'index.html')
    
    return "File not found", 404

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

@app.route('/admin', methods=['GET'])
@auth.login_required
def admin_page():
    return send_from_directory(app.static_folder, 'admin.html')

@app.route('/admin/submissions', methods=['GET'])
@auth.login_required
def view_submissions():
    try:
        submissions = load_submissions()
        if submissions:
            submissions.sort(key=lambda x: x.get('submitted_at', ''), reverse=True)
        return jsonify(submissions)
    except Exception as e:
        print(f"Error in view_submissions: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/admin/export', methods=['GET'])
@auth.login_required
def export_submissions():
    submissions = load_submissions()
    
    csv_content = "ID,Name,Email,Message,Submitted At,Status,Admin Comment\n"
    for sub in submissions:
        message = sub['message'].replace('"', '""')
        comment = sub.get('admin_comment', '').replace('"', '""')
        csv_content += f"{sub['id']},{sub['name']},{sub['email']},\"{message}\",{sub['submitted_at']},{sub.get('status', 'new')},\"{comment}\"\n"
    
    response = make_response(csv_content)
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=submissions.csv'
    return response

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
        if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            return jsonify({'error': 'Invalid file type'}), 400

        timestamp = int(datetime.now().timestamp())
        upload_filename = secure_filename(f"{timestamp}_{file.filename}")
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], upload_filename)
        file.save(upload_path)

        img = Image.open(upload_path)
        
        if YOLO_AVAILABLE:
            try:
                model_path = os.path.join(Path(__file__).parent.parent, "src", "models", "yolo", "best.pt")
                if os.path.exists(model_path):
                    model = YOLO(model_path)
                    results = model(img)
                    result = results[0]
                    
                    num_ships = len([box for box in result.boxes if box.conf >= 0.3])
                    
                    processed_img = Image.fromarray(result.plot())
                else:
                    num_ships = 0
                    processed_img = img
            except Exception as e:
                print(f"YOLO processing error: {e}")
                num_ships = 0
                processed_img = img
        else:
            num_ships = 0
            processed_img = img
            
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
            data = request.get_json()
            if not data or 'image_data' not in data:
                return jsonify({'error': 'No image data provided'}), 400
            
            image_data = data['image_data'].split(',')[1]
            image_bytes = base64.b64decode(image_data)
            
            filename = data.get('filename', f"{int(datetime.now().timestamp())}_detection.jpg")
            filepath = os.path.join(app.config['PROCESSED_FOLDER'], filename)
            
            with open(filepath, 'wb') as f:
                f.write(image_bytes)
            
            return jsonify({
                'message': 'Processed image saved successfully',
                'saved_path': url_for('serve_processed_image', filename=filename),
                'download_url': url_for('download_processed_image', filename=filename)
            })
        else:
            if 'file' not in request.files:
                return jsonify({'error': 'No file uploaded'}), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No selected file'}), 400
            
            filename = request.form.get('filename', secure_filename(f"{int(datetime.now().timestamp())}_{file.filename}"))
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
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
    try:
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
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            
            if max(width, height) <= max_size:
                return image_path
            
            if width > height:
                new_width = max_size
                new_height = int(height * max_size / width)
            else:
                new_height = max_size
                new_width = int(width * max_size / height)
            
            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            resized_img.save(image_path, quality=85, optimize=True)
            
            print(f"📏 Image resized from {width}x{height} to {new_width}x{new_height}")
            return image_path
            
    except Exception as e:
        print(f"⚠️ Image resize failed: {e}")
        return image_path

def get_sar_client():
    """Get or establish connection to SAR analysis service."""
    global _active_client, _active_service_url
    if _active_client and _active_service_url:
        try:
            print(f"🔄 Testing connection to {_active_service_url}")
            return _active_client, _active_service_url
        except Exception:
            _active_client = None
            _active_service_url = None
    from gradio_client import Client
    space_url = "https://faethon88-sar-imaging.hf.space"
    hf_token = os.getenv('HF_TOKEN')
    try:
        print(f"🔌 Connecting to: {space_url}")
        client = Client(space_url, hf_token=hf_token)
        print("✅ Client created successfully")
        _active_client = client
        _active_service_url = space_url
        return client, space_url
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return None, None

def wait_for_space_ready(space_url: str, timeout: int = None, interval: int = None) -> bool:
    """Poll the Hugging Face Space URL until it's awake or timeout reached.

    The Space (Gradio) will return a placeholder page or 503 while cold-starting.
    We look for known phrases indicating wake-up in progress and retry.

    Environment variables to override defaults:
      SPACE_WAKE_TIMEOUT  (seconds, default 120)
      SPACE_WAKE_INTERVAL (seconds, default 5)
    """
    timeout = timeout or int(os.getenv('SPACE_WAKE_TIMEOUT', '120'))
    interval = interval or int(os.getenv('SPACE_WAKE_INTERVAL', '5'))
    start = time.time()
    sleeping_markers = [
        'space is being prepared',
        'please wait',
        'starting up',
        'loading your app'
    ]
    print(f"🛌 Checking if Space is awake (timeout={timeout}s, interval={interval}s)...")
    attempts = 0
    while time.time() - start < timeout:
        attempts += 1
        try:
            # Use GET (HEAD sometimes returns 405 depending on hosting settings)
            resp = requests.get(space_url, timeout=10)
            code = resp.status_code
            lower_text = resp.text.lower() if resp.text else ''
            if code == 200:
                if any(marker in lower_text for marker in sleeping_markers):
                    print(f"⏳ Space cold-start in progress (attempt {attempts}, HTTP 200 sleeping page). Waiting {interval}s...")
                else:
                    print(f"✅ Space awake after {round(time.time()-start,2)}s (attempt {attempts})")
                    return True
            elif code in (503, 502, 504):
                print(f"⏳ Space not ready (HTTP {code}) attempt {attempts}; sleeping...")
            else:
                # Unexpected status; may still be waking, keep polling
                print(f"⚠️ Received HTTP {code} attempt {attempts}; continuing to poll.")
        except Exception as e:
            print(f"⚠️ Poll error attempt {attempts}: {e}")
        time.sleep(interval)
    print(f"❌ Space did not wake within {timeout}s.")
    return False

@app.route('/analyze-sar', methods=['POST'])
def analyze_sar():
    """
    Upload an image, send to HF Gradio Space, get annotated image + summary.
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    try:
        from PIL import Image
        from io import BytesIO
        import base64

        # 1. Get confidence value
        confidence = float(request.form.get('confidence', 0.5))
        filename = secure_filename(file.filename)
        # Ensure filename ends with .png for Gradio compatibility
        if not filename.lower().endswith('.png'):
            filename += '.png'

        # 2. Save uploaded image locally
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # 3. Connect to SAR Space
        client, space_url = get_sar_client()
        if not client:
            return jsonify({'error': 'SAR Space unavailable'}), 503

        # 3b. Ensure Space is awake before first predict to avoid cold-start errors
        wake_start = time.time()
        if not wait_for_space_ready(space_url):
            waited = time.time() - wake_start
            return jsonify({
                'error': 'SAR Space cold start timeout',
                'details': f'Waited {int(waited)}s for Space to wake. Try again shortly.',
                'space_used': space_url,
                'space_wake_wait_seconds': int(waited)
            }), 504
        wake_wait = time.time() - wake_start

        # 4. Call Gradio API with file using handle_file
        # gradio_client.handle_file() creates the proper payload format
        from gradio_client import handle_file
        
        api_variants = ["/predict", "predict"]
        result = None
        last_exc = None
        # Retry predict within wake window in case Space turns ready during first attempts
        predict_timeout = int(os.getenv('SPACE_PREDICT_TIMEOUT', os.getenv('SPACE_WAKE_TIMEOUT', '120')))
        poll_interval = int(os.getenv('SPACE_WAKE_INTERVAL', '5'))
        predict_start = time.time()
        attempt = 0
        while (time.time() - predict_start) < predict_timeout and result is None:
            attempt += 1
            for api_name in api_variants:
                try:
                    print(f"🔁 [attempt {attempt}] Gradio API api_name='{api_name}' using handle_file")
                    result = client.predict(handle_file(filepath), confidence, api_name=api_name)
                    print(f"✅ Gradio call succeeded with api_name='{api_name}' on attempt {attempt}")
                    break
                except Exception as e:
                    msg = str(e)
                    print(f"❌ api_name='{api_name}' failed on attempt {attempt}: {msg}")
                    last_exc = e
                    if "Cannot find a function with `api_name`" in msg:
                        # try next variant immediately
                        continue
                    # Errors likely due to cold start or gateway -> wait and retry
                    if any(k in msg for k in [
                        '503', '502', '504', 'Service Unavailable', 'Bad Gateway', 'Failed to fetch', 'Connection aborted'
                    ]):
                        print(f"⏳ Likely cold-start/network transient. Waiting {poll_interval}s before retry...")
                        time.sleep(poll_interval)
                        # break the for-loop to restart api variants next while iteration
                        break
                    # Non-retryable error -> break out fully
                    break

            # If still no result, try without api_name as an additional variant
            if result is None:
                try:
                    print(f"🔁 [attempt {attempt}] Gradio API without api_name (fallback)")
                    result = client.predict(handle_file(filepath), confidence)
                    print(f"✅ Gradio call succeeded without api_name on attempt {attempt}")
                except Exception as e:
                    msg = str(e)
                    print(f"❌ Fallback (no api_name) failed on attempt {attempt}: {msg}")
                    last_exc = e
                    if any(k in msg for k in [
                        '503', '502', '504', 'Service Unavailable', 'Bad Gateway', 'Failed to fetch', 'Connection aborted'
                    ]):
                        print(f"⏳ Waiting {poll_interval}s then retrying predict...")
                        time.sleep(poll_interval)
                        continue
                    # otherwise, break out as non-retryable
                    break

        if result is None:
            # Provide the last exception message to the caller for debugging
            err_msg = str(last_exc) if last_exc else "Unknown error"
            return jsonify({'error': f'SAR Space processing failed: {err_msg}'}), 502

        if not isinstance(result, (list, tuple)) or len(result) < 2:
            return jsonify({'error': 'Unexpected SAR Space response'}), 500

        annotated_image, summary = result[0], result[1]

        # 6. Handle different annotated image formats
        print(f"DEBUG: annotated_image type: {type(annotated_image)}")
        
        # Handle numpy array
        if isinstance(annotated_image, np.ndarray):
            print("DEBUG: Converting numpy array to data URI")
            pil_annotated = Image.fromarray(annotated_image.astype(np.uint8))
            buffered = BytesIO()
            pil_annotated.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
            annotated_image = f"data:image/png;base64,{img_str}"
        # Handle PIL Image
        elif isinstance(annotated_image, Image.Image):
            print("DEBUG: Converting PIL.Image to data URI")
            buffered = BytesIO()
            annotated_image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
            annotated_image = f"data:image/png;base64,{img_str}"
        # Handle file path from Gradio
        elif isinstance(annotated_image, str) and not annotated_image.startswith("data:image"):
            print(f"DEBUG: Got file path from Space: {annotated_image}")
            # If it's a path, try to read and convert it
            try:
                if os.path.exists(annotated_image):
                    with Image.open(annotated_image) as img:
                        buffered = BytesIO()
                        img.save(buffered, format="PNG")
                        img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
                        annotated_image = f"data:image/png;base64,{img_str}"
                else:
                    # It might be a URL or temp file - try to download/read
                    print(f"DEBUG: File path doesn't exist locally, treating as remote: {annotated_image}")
                    import requests
                    response = requests.get(annotated_image)
                    img = Image.open(BytesIO(response.content))
                    buffered = BytesIO()
                    img.save(buffered, format="PNG")
                    img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
                    annotated_image = f"data:image/png;base64,{img_str}"
            except Exception as e:
                print(f"ERROR: Failed to process image path: {e}")
                return jsonify({'error': f'Failed to process returned image: {str(e)}'}), 500
        # Handle data URI (already in correct format)
        elif isinstance(annotated_image, str) and annotated_image.startswith("data:image"):
            print("DEBUG: Already in data URI format")
            pass
        else:
            print(f"ERROR: Unexpected image type: {type(annotated_image)}")
            return jsonify({'error': f'Annotated image in unexpected format: {type(annotated_image)}'}), 500

        # 7. Save annotated image locally
        processed_filename = f"{int(datetime.now().timestamp())}_result.png"
        processed_path = os.path.join(app.config['PROCESSED_FOLDER'], processed_filename)
        if isinstance(annotated_image, str) and annotated_image.startswith("data:image"):
            img_data = annotated_image.split(",")[1]
            with open(processed_path, "wb") as f:
                f.write(base64.b64decode(img_data))
        else:
            return jsonify({'error': 'Annotated image missing'}), 500

        return jsonify({
            'success': True,
            'confidence': confidence,
            'detection_summary': summary,
            'annotated_image_url': url_for('serve_processed_image', filename=processed_filename),
            'download_url': url_for('download_processed_image', filename=processed_filename),
            'uploaded_image_url': url_for('serve_uploaded_image', filename=filename),
            'original_filename': filename,
            'processed_at': datetime.now().isoformat(),
            'space_used': space_url or 'unknown',
            'space_wake_wait_seconds': int(wake_wait)
        })
    except Exception as e:
        return jsonify({'error': f"SAR Space processing failed: {str(e)}"}), 500

@app.route('/open-space', methods=['GET'])
def open_space():
    hf_space_url = os.getenv('HF_SPACE_URL', 'https://huggingface.co/spaces/Faethon88/sar_imaging')
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

@app.route('/sar-status', methods=['GET'])
def sar_status():
    try:
        client, active_url = get_sar_client()
        
        services = {
            'huggingface_space': {'url': 'https://huggingface.co/spaces/Faethon88/sar_imaging', 'status': 'unknown'},
            'local_server': {'url': 'http://127.0.0.1:7860', 'status': 'unknown'}
        }
        
        if client and active_url:
            if 'huggingface' in active_url:
                services['huggingface_space']['status'] = 'available (active)'
                services['local_server']['status'] = 'not tested (HF working)'
            else:
                services['local_server']['status'] = 'available (active)'
                services['huggingface_space']['status'] = 'unavailable (using local fallback)'
        else:
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

@app.route('/sar-connect', methods=['POST'])
def sar_connect():
    try:
        global _active_client, _active_service_url
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

@app.route('/hf-status', methods=['GET'])
def hf_status():
    """Return non-sensitive Hugging Face config status"""
    hf_token_present = bool(os.getenv('HF_TOKEN'))
    hf_model = os.getenv('HF_MODEL') or None
    return jsonify({
        'hf_token_present': hf_token_present, 
        'hf_model': hf_model
    }), 200

if __name__ == '__main__':
    if not os.path.exists(os.path.join(basedir, 'instance')):
        os.makedirs(os.path.join(basedir, 'instance'))
    
    print("🚀 Starting SAR Analysis Website...")
    initialize_sar_connection()
    
    print("🌐 Starting Flask server...")
    app.run(host='0.0.0.0', port=5000, debug=True)