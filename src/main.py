import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, request, jsonify
# Import the db instance and the model
from src.models.contact_submission import db, ContactSubmission
# Import for email sending (placeholder)
import smtplib
from email.mime.text import MIMEText

# Initialize Flask app, pointing static folder to 'static' directory
# Also specify the instance_path
app = Flask(__name__, 
            static_folder=os.path.join(os.path.dirname(__file__), 'static'),
            instance_relative_config=True, # Allows loading config relative to instance folder
            instance_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance')) # Define instance folder path

app.config['SECRET_KEY'] = 'a_secure_temporary_secret_key' # Replace with a proper secret key if needed

# Ensure the instance folder exists
try:
    os.makedirs(app.instance_path)
except OSError:
    pass # Already exists

# --- Database Configuration (Changed to SQLite) ---
# Define the path for the SQLite database file within the instance folder
sqlite_db_path = os.path.join(app.instance_path, 'contact_submissions.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{sqlite_db_path}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Initialize the database with the app
db.init_app(app)

# Create database tables if they don't exist
with app.app_context():
    db.create_all()
# --- End Database Configuration ---

# Route to serve static files (HTML, CSS, JS) and the index page
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
            return "Static folder not configured", 404

    # If path is specified and exists, serve the file (e.g., /about serves about.html)
    if path != "" and os.path.exists(os.path.join(static_folder_path, path + '.html')):
        return send_from_directory(static_folder_path, path + '.html')
    # If path is specified and it's a file like style.css or an image/video
    elif path != "" and os.path.exists(os.path.join(static_folder_path, path)):
         return send_from_directory(static_folder_path, path)
    # Otherwise, serve index.html for the root path or if the path is empty
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404

# Route to handle contact form submission (POST request)
@app.route('/submit_contact', methods=['POST'])
def handle_contact_form():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')

        # Ensure all fields are filled
        if not name or not email or not message:
            return jsonify({'status': 'error', 'message': 'All fields are required.'}), 400

        # Validate email format
        if '@' not in email or '.' not in email.split('@')[-1]:
            return jsonify({'status': 'error', 'message': 'Invalid email format.'}), 400

        # --- Check if email already exists in the database ---
        existing_submission = ContactSubmission.query.filter_by(email=email).first()
        if existing_submission:
            return jsonify({'message': 'Error saving submission: Email already exists in the database.'}), 400

        # --- Store data in Database ---
        try:
            submission = ContactSubmission(name=name, email=email, message=message)
            db.session.add(submission)
            db.session.commit()
            db_success = True
            print(f"Successfully saved submission from {name} to our database.")
        except Exception as e:
            db.session.rollback()
            db_success = False
            print(f"Error saving submission to our database: {e}")
        # --- End Database Storage ---

        # Return a response indicating success/failure
        if db_success:
            response_message = 'Form submitted successfully and saved to database.'
            return jsonify({'message': response_message})
        else:
            return jsonify({'message': 'Failed to save submission to database.'}), 500

    else:
        return jsonify({'status': 'error', 'message': 'Method not allowed'}), 405

if __name__ == '__main__':
    # Run the app on 0.0.0.0 to make it accessible externally
    # Debug mode is useful for development but should be False for production/sharing
    app.run(host='0.0.0.0', port=5000, debug=True) 

    
