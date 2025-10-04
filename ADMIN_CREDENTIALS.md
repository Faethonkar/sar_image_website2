# SAR Image Website - Admin Credentials & Configuration

## 🔐 Admin Panel Access

### Current Credentials (from .env file):
- **URL:** `http://localhost:5000/admin`
- **Username:** `admin`
- **Password:** `dbf_admin_2025`

### How to Change Credentials:
Edit the `.env` file in the root directory and modify:
```
ADMIN_USERNAME=your_new_username
ADMIN_PASSWORD=your_new_password
```

## 📁 Files Created/Modified:

### 1. `.env` file (NEW)
- Contains all environment variables
- **IMPORTANT:** Never commit this file to version control
- Add `.env` to your `.gitignore` file

### 2. `src/main.py` (MODIFIED)
- Added python-dotenv support
- Updated admin authentication to use environment variables
- Removed automatic email sending from contact form

### 3. `src/static/admin.html` (NEW)
- Professional admin dashboard
- Shows all contact submissions
- Export to CSV functionality
- Real-time data refresh

## 🚀 Features:

### Contact Form:
- ✅ Saves all messages to database
- ✅ No automatic emails sent
- ✅ Simple success confirmation

### Admin Panel:
- ✅ Secure login required
- ✅ View all contact submissions
- ✅ Statistics dashboard
- ✅ Export data to CSV
- ✅ Responsive design

## 🔧 Environment Variables:

```
ADMIN_USERNAME=admin
ADMIN_PASSWORD=dbf_admin_2025
SECRET_KEY=your_super_secure_secret_key_here_change_this
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=dbf.infocontact@gmail.com
MAIL_PASSWORD=wgvk fzaf fzvj onmz
MAIL_DEFAULT_SENDER=dbf.infocontact@gmail.com
FLASK_ENV=development
FLASK_DEBUG=false
```

## 📋 To Access Admin Panel:

1. Start the Flask application: `python src/main.py`
2. Open browser to: `http://localhost:5000/admin`
3. Enter credentials:
   - Username: `admin`
   - Password: `dbf_admin_2025`
4. View and manage all contact submissions

## 🔒 Security Notes:

- Change the default SECRET_KEY in production
- Use strong passwords for admin access
- Keep the .env file secure and never share it
- Consider using environment-specific configurations for production

## 📦 Dependencies Added:
- `python-dotenv` - For loading environment variables from .env file