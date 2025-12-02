# 🌐 Quick Apply Web App - Launch Guide

## 📋 Prerequisites

1. **Python 3.8+** installed
2. **All dependencies** installed
3. **API keys** configured (Gemini/OpenAI/Ollama)
4. **Resume file** at `input/resume.yml`

## 🚀 Quick Start (3 Steps)

### Step 1: Install Flask Dependencies

```bash
cd /Users/bhavananare/github/webapp/resume_py-master

# Install Flask and CORS
pip3 install flask flask-cors
```

### Step 2: Verify Configuration

```bash
# Check if config.json exists
ls -la config.json

# Check if resume exists
ls -la input/resume.yml

# Check if API key is set
echo $GEMINI_API_KEY
# OR
echo $OPENAI_API_KEY
```

### Step 3: Launch the Web App

```bash
# Start the server
python3 web_app.py
```

You should see:
```
🚀 Quick Apply Web App Starting...
📝 Make sure config.json is configured with API keys
📄 Make sure input/resume.yml exists

🌐 Open http://localhost:5000 in your browser

Press Ctrl+C to stop

 * Running on http://0.0.0.0:5000
```

### Step 4: Open in Browser

Open your web browser and navigate to:
```
http://localhost:5000
```

## 🎯 How to Use the Web App

### Option 1: From Job Link

1. **Click "From Job Link" tab** (default)
2. **Paste job URL** (e.g., `https://boards.greenhouse.io/stripe/jobs/123`)
3. **(Optional)** Enter Company Name and Job Title
4. **Click "Generate Resume & Cover Letter"**
5. **Wait 30-60 seconds** for AI to generate documents
6. **Download PDFs and DOCX files**

### Option 2: From Job Description

1. **Click "From Description" tab**
2. **Paste full job description** in the text area
3. **Enter Company Name** (e.g., "Google")
4. **Enter Job Title** (e.g., "ML Engineer")
5. **Click "Generate Resume & Cover Letter"**
6. **Wait 30-60 seconds** for AI to generate documents
7. **Download PDFs and DOCX files**

## 📊 What You'll See

### 1. Loading Screen
```
Generating Your Documents...
This may take 30-60 seconds. Please wait.
```

### 2. Results Screen
```
Match Score
   78.5%
🟢 Excellent Match!

📌 Job Details
Company: Stripe
Position: Senior Software Engineer

📄 Download Your Documents
[Resume] Download PDF | Download DOCX | Preview PDF
[Cover Letter] Download PDF | Download DOCX | Preview PDF
```

## 🔧 Advanced Setup

### Running on a Different Port

```bash
# Edit web_app.py, change the last line:
app.run(debug=True, host='0.0.0.0', port=8080)  # Use port 8080

# Or set environment variable
export FLASK_RUN_PORT=8080
python3 web_app.py
```

### Running in Production Mode

```bash
# Install production server
pip3 install gunicorn

# Run with gunicorn (more stable for production)
gunicorn -w 4 -b 0.0.0.0:5000 web_app:app
```

### Running in Background

```bash
# Option 1: Using nohup
nohup python3 web_app.py > web_app.log 2>&1 &

# Check if running
ps aux | grep web_app.py

# View logs
tail -f web_app.log

# Stop
pkill -f web_app.py
```

```bash
# Option 2: Using tmux (recommended)
tmux new -s webapp
python3 web_app.py

# Detach: Press Ctrl+B, then D
# Reattach: tmux attach -t webapp
# Kill: tmux kill-session -t webapp
```

### Accessing from Other Devices on Your Network

```bash
# Find your local IP
ifconfig | grep "inet " | grep -v 127.0.0.1

# Example output: 192.168.1.100

# Start the app (already configured for 0.0.0.0)
python3 web_app.py

# Access from other devices:
# http://192.168.1.100:5000
```

## 🌍 Deploying to the Internet

### Option 1: Deploy to Heroku (Free/Paid)

```bash
# Install Heroku CLI
# https://devcenter.heroku.com/articles/heroku-cli

# Login
heroku login

# Create app
heroku create my-quick-apply-app

# Set environment variables
heroku config:set GEMINI_API_KEY=your_api_key_here

# Create Procfile
echo "web: gunicorn web_app:app" > Procfile

# Create requirements.txt (if not exists)
pip3 freeze > requirements.txt

# Deploy
git add .
git commit -m "Deploy web app"
git push heroku main

# Open in browser
heroku open
```

### Option 2: Deploy to Railway.app (Easy)

1. Go to https://railway.app
2. Click "New Project" → "Deploy from GitHub"
3. Select your repository
4. Add environment variables:
   - `GEMINI_API_KEY` or `OPENAI_API_KEY`
5. Railway auto-detects Flask and deploys
6. Get your public URL: `https://your-app.railway.app`

### Option 3: Deploy to Render.com (Free)

1. Go to https://render.com
2. Click "New" → "Web Service"
3. Connect your GitHub repo
4. Configure:
   - **Name:** `quick-apply`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn web_app:app`
5. Add environment variables
6. Deploy!

### Option 4: Using ngrok (Quick Testing)

```bash
# Install ngrok
# https://ngrok.com/download

# Start your app
python3 web_app.py

# In another terminal, expose it
ngrok http 5000

# You'll get a public URL like:
# https://abc123.ngrok.io
```

## 🔐 Security Considerations

### For Public Deployment:

1. **Add Authentication**
   ```python
   # Add to web_app.py
   from flask_httpauth import HTTPBasicAuth
   auth = HTTPBasicAuth()
   
   @auth.verify_password
   def verify_password(username, password):
       return username == 'admin' and password == 'your_secure_password'
   
   @app.route('/')
   @auth.login_required
   def index():
       return render_template('index.html')
   ```

2. **Use HTTPS** (automatic with Heroku/Railway/Render)

3. **Set Environment Variables** (never commit API keys)
   ```bash
   # On server
   export GEMINI_API_KEY=your_key_here
   export SECRET_KEY=random_secret_for_sessions
   ```

4. **Add Rate Limiting**
   ```bash
   pip3 install flask-limiter
   ```
   ```python
   from flask_limiter import Limiter
   limiter = Limiter(app, default_limits=["100 per hour"])
   ```

## 📁 File Structure

```
resume_py-master/
├── web_app.py                 # Flask backend
├── templates/
│   └── index.html            # Web interface
├── static/                   # (optional) CSS/JS files
├── output/
│   ├── web_uploads/          # Uploaded files
│   └── web_output/           # Generated documents
├── config.json               # Configuration
├── input/
│   └── resume.yml           # Your resume
└── requirements.txt         # Python dependencies
```

## 🐛 Troubleshooting

### Problem: "Address already in use"

```bash
# Find process using port 5000
lsof -i :5000

# Kill it
kill -9 <PID>

# Or use a different port
# Edit web_app.py line: app.run(..., port=5001)
```

### Problem: "Module not found: flask"

```bash
pip3 install flask flask-cors
```

### Problem: "config.json not found"

```bash
# Make sure you're in the correct directory
cd /Users/bhavananare/github/webapp/resume_py-master
python3 web_app.py
```

### Problem: "Failed to generate documents"

```bash
# Check API keys
echo $GEMINI_API_KEY
echo $OPENAI_API_KEY

# Check config.json
cat config.json | grep -A 5 "gemini"

# Check logs in terminal
# Look for error messages in the Flask output
```

### Problem: Can't access from other devices

```bash
# Make sure the app is running on 0.0.0.0, not 127.0.0.1
# In web_app.py, the line should be:
app.run(debug=True, host='0.0.0.0', port=5000)

# Check firewall settings
# Allow port 5000 in your firewall
```

## 📊 Monitoring

### View Real-Time Logs

```bash
# If running in foreground, you'll see logs directly

# If running in background with nohup
tail -f web_app.log

# If using tmux
tmux attach -t webapp
```

### Check Health Endpoint

```bash
# Test if the app is running
curl http://localhost:5000/api/health

# Expected response:
{
  "status": "ok",
  "config_loaded": true,
  "llm_providers": {
    "gemini": true,
    "openai": false,
    "ollama": false
  }
}
```

## 🎨 Customization

### Change Colors/Theme

Edit `templates/index.html`, find the `<style>` section:

```css
/* Change primary color gradient */
background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
/* Change to your preferred colors */
background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
```

### Add Logo

```html
<!-- In templates/index.html, inside .header -->
<div class="header">
    <img src="/static/logo.png" alt="Logo" style="height: 60px;">
    <h1>🚀 Quick Apply</h1>
    ...
</div>
```

### Customize Output Directory

```python
# In web_app.py
app.config['OUTPUT_FOLDER'] = 'my_custom_output'
```

## 🚦 Performance Tips

1. **Use Production Server (Gunicorn)**
   ```bash
   pip3 install gunicorn
   gunicorn -w 4 web_app:app
   ```

2. **Enable Caching** for repeat generations

3. **Use Background Tasks** (Celery) for long-running jobs

4. **Add CDN** for static assets

## 📱 Mobile-Friendly

The web interface is already responsive and works on:
- ✅ Desktop browsers
- ✅ Tablets
- ✅ Mobile phones (iOS/Android)

## 🔄 Updates and Maintenance

### Update the App

```bash
# Pull latest changes
git pull

# Restart the server
pkill -f web_app.py
python3 web_app.py
```

### Clear Old Generated Files

```bash
# Clean up old files (older than 7 days)
find output/web_output -type f -mtime +7 -delete
```

## 📞 Support

If you encounter issues:

1. Check terminal logs for error messages
2. Verify API keys are set correctly
3. Ensure `input/resume.yml` exists
4. Test with command-line tool first: `python3 quick_apply.py --help`

---

## 🎉 Quick Commands Summary

```bash
# Launch web app
python3 web_app.py

# Access locally
open http://localhost:5000

# Access from network
open http://$(ipconfig getifaddr en0):5000

# Run in background
nohup python3 web_app.py > web_app.log 2>&1 &

# Stop background process
pkill -f web_app.py

# View logs
tail -f web_app.log
```

**Enjoy your Quick Apply Web App! 🚀**

