# DBF Science Technology Website

A multi-page website for DBF Science Technology with Greek/English language support.

## 🛠️ Technology Stack

- **Backend**: Flask (Python)
- **Deployment**: Railway
- **UI**: Vanilla HTML/CSS/JS with multi-language support

## 📁 Project Structure

```
dbf_site/
├── src/
│   ├── main.py                   # Flask server
│   └── static/                   # HTML, CSS, JS, images
├── requirements.txt              # Python dependencies
├── Procfile                      # Railway deployment configuration
└── README.md                     # This file
```

## 🔧 Local Development

### Prerequisites
- Python 3.8+

### Setup

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Run the development server:**
```bash
cd src
python main.py
```

3. **Access the application:**
- Website: http://127.0.0.1:5000

## 🌐 Railway Deployment

```bash
git add .
git commit -m "Deploy"
git push origin main
```

Then connect the repo in [Railway.app](https://railway.app). The `Procfile` handles startup automatically.

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `PORT` | Server port (set by Railway) | Auto |
| `SECRET_KEY` | Flask secret key | Optional |
| `ADMIN_USERNAME` | Admin panel username | Optional |
| `ADMIN_PASSWORD` | Admin panel password | Optional |

## 🔐 Admin Panel

- URL: `/admin`
- Default credentials set via `ADMIN_USERNAME` / `ADMIN_PASSWORD` env vars

## 📞 Contact

- **Website**: [DBF Science Technology](https://www.dbfsciencetechnology.gr)


## 📁 Project Structure

```
sar_image_website_local/
├── src/                          # Main Flask application
│   ├── main.py                   # Flask server with auto-connection
│   ├── static/                   # Static files (CSS, images, HTML)
│   │   ├── technology.html       # SAR analysis interface
│   │   ├── uploads/              # Uploaded images (runtime)
│   │   └── processed/            # Processed results (runtime)
│   └── models/                   # Data models
├── improved_gradio_app.py        # Enhanced Gradio SAR analysis server
├── railway_start.py              # Production startup script
├── requirements.txt              # Python dependencies
├── Procfile                      # Railway deployment configuration
└── README.md                     # This file
```

## 🔧 Local Development

### Prerequisites
- Python 3.8+
- Git

### Setup

1. **Clone the repository:**
```bash
git clone https://github.com/Faethonkar/sar_image_website2.git
cd sar_image_website2
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Start the development servers:**
```bash
# Terminal 1 - Flask website
cd src
python main.py

# Terminal 2 - Gradio SAR analysis
python improved_gradio_app.py
```

4. **Access the application:**
- Website: http://127.0.0.1:5000
- SAR Analysis: http://127.0.0.1:5000/technology
- Gradio Direct: http://127.0.0.1:7860

## 🌐 Railway Deployment

### Step 1: Prepare Repository
```bash
git add .
git commit -m "Deploy SAR analysis website"
git push origin main
```

### Step 2: Deploy to Railway
1. Go to [Railway.app](https://railway.app)
2. Connect your GitHub account
3. Click "New Project" → "Deploy from GitHub repo"
4. Select your repository: `Faethonkar/sar_image_website2`
5. Railway will automatically detect and deploy using `railway_start.py`

### Step 3: Environment Variables (Optional)
Set in Railway dashboard:
- `HF_TOKEN`: Your Hugging Face token (for private models)
- `FLASK_ENV`: `production`

### Step 4: Custom Domain (Optional)
- In Railway dashboard → Settings → Domains
- Add your custom domain or use the provided Railway URL

## 🔐 Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `PORT` | Server port (set by Railway) | Auto |
| `HF_TOKEN` | Hugging Face API token | Optional |
| `FLASK_ENV` | Flask environment mode | Optional |

## 🎯 Usage

1. **Visit the website** at your Railway URL
2. **Navigate to Technology page** or go directly to `/technology`
3. **Upload a SAR image** using the analysis form
4. **View results** with:
   - Original image on the left
   - Annotated detection results on the right
   - Detection summary showing ship and aircraft counts

## 🤖 AI Model Details

- **Model**: YOLO v8 trained on SAR imagery
- **Classes**: Ships, Aircraft
- **Source**: Hugging Face Model Hub (`Faethon88/sar`)
- **Fallback**: Automatic failover between HF Space and local processing

## 🔧 API Endpoints

- `GET /`: Main website homepage
- `GET /technology`: SAR analysis interface
- `POST /analyze-sar`: Process uploaded SAR image
- `GET /sar-status`: Check analysis service availability
- `POST /sar-connect`: Establish service connection

## 📝 License

MIT License - See LICENSE file for details

## 👥 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📞 Contact

- **GitHub**: [@Faethonkar](https://github.com/Faethonkar)
- **Website**: [DBF Science Technology](https://www.dbfsciencetechnology.gr)
- **Email**: Contact through GitHub issues

## 🙏 Acknowledgments

- SAR imagery providers (ESA, ICEYE)
- Hugging Face for model hosting
- YOLO/Ultralytics for detection framework
- Railway for deployment platform

---

**Built with ❤️ for maritime and aerospace surveillance**