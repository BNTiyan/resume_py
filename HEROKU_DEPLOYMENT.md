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

## 6. Deploying via Heroku Dashboard (Step-by-Step)
If you prefer identifying and clicking through the UI:

### A. Create the App
1. Log in to [dashboard.heroku.com](https://dashboard.heroku.com/).
2. Click **New** -> **Create new app**.
3. Name your app (e.g., `quick-apply-agent`) and click **Create app**.

### B. Connect to GitHub
1. Go to the **Deploy** tab in your app's dashboard.
2. Select **GitHub** as the deployment method.
3. Search for your repository name and click **Connect**.

### C. Configure Buildpacks (UI Method)
1. Go to the **Settings** tab.
2. Scroll down to the **Buildpacks** section.
3. Click **Add buildpack** and add these in order:
   - `heroku/python`
   - `https://github.com/heroku/heroku-buildpack-google-chrome`
   - `https://github.com/heroku/heroku-buildpack-chromedriver`

### D. Set Config Vars (UI Method)
1. Still in the **Settings** tab, click **Reveal Config Vars**.
2. Add your keys:
   - `GEMINI_API_KEY`: your_key_here
   - `LLM_PROVIDER`: `gemini`
   - `SERPAPI_KEY`: your_key_here (optional)

### E. Manual Deploy
1. Go back to the **Deploy** tab.
2. Scroll to the bottom and click **Deploy Branch** (ensure `main` is selected).
3. Wait for the build to finish.

## 7. Verify Deployment
Once the build is complete, click **Open App** at the top right of the dashboard.
You can monitor logs using:
```bash
heroku logs --tail
```

## 💡 Troubleshooting
- **Memory Issues**: If the app crashes on build, try simplifying `requirements.txt` by commenting out heavy dependencies like `faiss-cpu`.
- **Chrome Error**: Ensure the buildpacks are added in the correct order (Python should be first).
- **No Jobs Found**: Ensure `SERPAPI_KEY` is set for better job discovery without Selenium issues.
