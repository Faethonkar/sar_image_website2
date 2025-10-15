import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'  # Add this line first
import sys
import json
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import base64
from io import BytesIO
import numpy as np
import torch
import torchvision

# Try to import YOLO - graceful fallback for deployment
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    print("Warning: ultralytics not available. YOLO ship detection will be disabled.")
    YOLO_AVAILABLE = False

# Try to import EfficientDet - graceful fallback for deployment
try:
    from effdet import get_efficientdet_config, EfficientDet, DetBenchTrain
    from effdet.efficientdet import HeadNet
    import effdet
    EFFICIENTDET_AVAILABLE = True
except ImportError:
    print("Warning: effdet not available. EfficientDet detection will be disabled.")
    EFFICIENTDET_AVAILABLE = False

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("python-dotenv not installed. Install it with: pip install python-dotenv")
    print("Environment variables will be loaded from system environment only.")


# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, request, jsonify, make_response, url_for
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

if __name__ == '__main__':
    # Create the instance directory if it doesn't exist
    if not os.path.exists(os.path.join(basedir, 'instance')):
        os.makedirs(os.path.join(basedir, 'instance'))
    
    app.run(host='0.0.0.0', port=5000, debug=False)