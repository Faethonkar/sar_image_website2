import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Initialize Flask app
app = Flask(__name__, static_folder="static")

# Configure PostgreSQL connection from environment variable
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "postgresql://localhost/default")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key_here'  # Change in production

# Initialize the database
db = SQLAlchemy(app)

# Define the model
class ContactSubmission(db.Model):
    __tablename__ = 'contact_submissions'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<ContactSubmission {self.email}>'

# Route for contact form submission
@app.route('/submit_contact', methods=['POST'])
def handle_contact_form():
    name = request.form.get('name')
    email = request.form.get('email')
    message = request.form.get('message')

    if not name or not email or not message:
        return jsonify({'status': 'error', 'message': 'All fields are required.'}), 400

    if '@' not in email or '.' not in email.split('@')[-1]:
        return jsonify({'status': 'error', 'message': 'Invalid email format.'}), 400

    existing_submission = ContactSubmission.query.filter_by(email=email).first()
    if existing_submission:
        return jsonify({'status': 'error', 'message': 'Email already exists in the database.'}), 400

    try:
        submission = ContactSubmission(name=name, email=email, message=message)
        db.session.add(submission)
        db.session.commit()
        return jsonify({'message': 'Form submitted successfully and saved to database.'}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Database error: {e}")
        return jsonify({'message': 'Failed to save submission to database.'}), 500

# Health check route (optional)
@app.route('/')
def index():
    return "Server is running!"

# Run the app
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
    
