import os
import sys
from datetime import datetime
from pathlib import Path
from PIL import Image
from flask_mail import Mail, Message
from ultralytics import YOLO
import tempfile


# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, request, jsonify, make_response, url_for
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from src.models.contact_submission import db, ContactSubmission

# Initialize Flask app
app = Flask(__name__, 
            static_folder=os.path.join(os.path.dirname(__file__), 'static'),
            instance_relative_config=True,
            instance_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance'))

# Configuration for SQLite (local database)
basedir = os.path.abspath(os.path.dirname(__file__))
instance_path = os.path.join(basedir, 'instance')

# Ensure the instance directory exists
Path(instance_path).mkdir(parents=True, exist_ok=True)

# Database configuration - using contact_submissions.db
db_path = os.path.join(instance_path, 'contact_submissions.db')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'a_secure_temporary_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Add these with your other configurations
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['PROCESSED_FOLDER'] = 'static/processed'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)

# Email configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', 'dbf.infocontact@gmail.com')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD', 'wgvk fzaf fzvj onmz ')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', 'dbf.infocontact@gmail.com')

# Initialize the database with the app
db.init_app(app)

# Initialize Flask-Mail
mail = Mail(app)

# Basic Authentication Setup
auth = HTTPBasicAuth()
users = {
    "admin": generate_password_hash(os.getenv('ADMIN_PASSWORD', 'defaultpassword'), method='pbkdf2:sha256')
}

@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username

# Create database tables if they don't exist
with app.app_context():
    try:
        db.create_all()
        print(f"Database created successfully at: {db_path}")
    except Exception as e:
        print(f"Error creating database: {str(e)}")
        raise

def send_confirmation_email(name, email, message):
    try:
        subject = "Thank you for contacting us"
        body = f"""Dear {name},

Thank you for reaching out to us. We have received your message and will get back to you soon.

Here's a copy of your message for your reference:
{message}

Best regards,
Your Company Name
"""
        msg = Message(subject=subject, recipients=[email], body=body)
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Error sending email: {str(e)}")
        return False

# Route to serve static files
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
        return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path + '.html')):
        return send_from_directory(static_folder_path, path + '.html')
    elif path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        return "index.html not found", 404

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

        existing_submission = ContactSubmission.query.filter_by(email=email).first()
        if existing_submission:
            return jsonify({'message': 'Error: Email already exists.'}), 400

        try:
            submission = ContactSubmission(name=name, email=email, message=message)
            db.session.add(submission)
            db.session.commit()
            
            # Send confirmation email
            email_sent = send_confirmation_email(name, email, message)
            if not email_sent:
                return jsonify({'message': 'Form submitted successfully but failed to send confirmation email.'}), 200
                
            return jsonify({'message': 'Form submitted successfully! A confirmation email has been sent.'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'message': f'Database error: {str(e)}'}), 500

    return jsonify({'status': 'error', 'message': 'Method not allowed'}), 405

# Admin route to view submissions (protected)
@app.route('/admin/submissions', methods=['GET'])
@auth.login_required
def view_submissions():
    submissions = ContactSubmission.query.order_by(ContactSubmission.submitted_at.desc()).all()
    submissions_data = [{
        'id': s.id,
        'name': s.name,
        'email': s.email,
        'message': s.message,
        'submitted_at': s.submitted_at.isoformat() if s.submitted_at else None
    } for s in submissions]
    return jsonify(submissions_data)

# Admin route to export submissions as CSV (protected)
@app.route('/admin/export', methods=['GET'])
@auth.login_required
def export_submissions():
    submissions = ContactSubmission.query.all()
    
    # Generate CSV content
    csv_content = "ID,Name,Email,Message,Submitted At\n"
    for sub in submissions:
        csv_content += f"{sub.id},{sub.name},{sub.email},\"{sub.message}\",{sub.submitted_at}\n"
    
    response = make_response(csv_content)
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=submissions.csv'
    return response

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

        # Create paths and ensure directories exist
        processed_dir = os.path.join(app.static_folder, 'processed')
        os.makedirs(processed_dir, exist_ok=True)
        
        # Create unique filename
        timestamp = int(datetime.now().timestamp())
        filename = secure_filename(f"{timestamp}_{file.filename}")
        processed_path = os.path.join(processed_dir, filename)
        
        # Process image
        img = Image.open(file.stream)
        model = YOLO(os.path.join(Path(__file__).parent.parent, "src", "models", "yolo", "best.pt"))
        results = model(img)
        result = results[0]
        
        # Get detection results
        num_ships = len([box for box in result.boxes if box.conf >= 0.3])
        
        # Save processed image
        processed_img = Image.fromarray(result.plot())
        processed_img.save(processed_path)

        # Return relative URL path
        return jsonify({
            'num_ships': num_ships,
            'processed_image': f"/static/processed/{filename}",
            'message': 'No ships detected' if num_ships == 0 else None
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/static/processed/<filename>')
def serve_processed_image(filename):
    processed_dir = os.path.join(app.static_folder, 'processed')
    return send_from_directory(processed_dir, filename)
        
if __name__ == '__main__':
    # Create the instance directory if it doesn't exist
    if not os.path.exists(os.path.join(basedir, 'instance')):
        os.makedirs(os.path.join(basedir, 'instance'))
    app.run(host='0.0.0.0', port=5000, debug=False)