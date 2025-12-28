# 🚀 Deploying Quick Apply to Heroku

Follow these steps to deploy your application to Heroku.

## 1. Prerequisites
- A Heroku account (Paid plan required: Basic or Eco).
- [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli) installed on your machine.
- Your code pushed to a GitHub repository or ready for local Heroku push.

## 2. Prepare Your Local Environment
Ensure you have the latest deployment files:
- `requirements.txt`: Includes all dependencies.
- `Procfile`: Set to `web: gunicorn web_app:app`.
- `runtime.txt`: Set to `python-3.11.7` (recommended).

## 3. Create the Heroku App
```bash
heroku login
heroku create quick-apply-agent # Replace with your app name
```

## 4. Set Buildpacks (Essential for Selenium)
If you want to use the Selenium-based scraping features, you MUST add these buildpacks:
```bash
heroku buildpacks:add heroku/python
heroku buildpacks:add https://github.com/heroku/heroku-buildpack-google-chrome
heroku buildpacks:add https://github.com/heroku/heroku-buildpack-chromedriver
```

## 5. Configure Environment Variables
Set your API keys in the Heroku dashboard or via CLI:
```bash
# Choose your preferred provider
heroku config:set GEMINI_API_KEY=your_gemini_key
heroku config:set LLM_PROVIDER=gemini

# Optional: OpenAI or SerpApi
heroku config:set OPENAI_API_KEY=your_openai_key
heroku config:set SERPAPI_KEY=your_serpapi_key
```

## 6. Deploy
### Option A: From local machine
```bash
git add .
git commit -m "Prepare for Heroku deployment"
git push heroku main
```

### Option B: From GitHub (Recommended)
1. Go to your app in the [Heroku Dashboard](https://dashboard.heroku.com/).
2. Navigate to **Deploy** tab.
3. Select **GitHub** as the deployment method.
4. Connect your repository and click **Deploy Branch**.

## 7. Verify Deployment
Once deployed, click **Open App** in Heroku.
You can monitor logs using:
```bash
heroku logs --tail
```

## 💡 Troubleshooting
- **Memory Issues**: If the app crashes on build, try simplifying `requirements.txt` by commenting out heavy dependencies like `faiss-cpu`.
- **Chrome Error**: Ensure the buildpacks are added in the correct order (Python should be first).
- **No Jobs Found**: Ensure `SERPAPI_KEY` is set for better job discovery without Selenium issues.
