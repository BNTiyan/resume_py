# Quick Start Guide

Get up and running with `resume_py` in 5 minutes.

## 1. Setup Environment

```bash
cd resume_py

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## 2. Configure API Keys

Create a `.env` file:

```bash
echo "OPENAI_API_KEY=your_openai_api_key_here" > .env
```

Or export directly:

```bash
export OPENAI_API_KEY=your_key_here
```

## 3. Prepare Your Resume

Create `input/resume.txt` with your resume content (plain text):

```
Your Name
City, Country | Phone | Email | LinkedIn | GitHub

PROFESSIONAL SUMMARY
Your summary here...

EXPERIENCE
Company Name | Role | Dates
- Achievement 1
- Achievement 2

SKILLS
Python, JavaScript, AWS, Docker, etc.
```

## 4. Choose Your Workflow

### A. Find Matching Jobs

```bash
# Edit config.json first to set your preferences
python match.py --config config.json
```

**Output**: 
- `output/matched_jobs_*.json` - Top job matches
- `output/cover_letters/` - Auto-generated cover letters
- `output/tailored_resumes/` - Tailored resumes

### B. Tailor Resume to Specific Job

Create `input/jd.txt` with the job description, then:

```bash
# Keyword-based (no API key needed)
python tailor.py \
  --resume input/resume.txt \
  --jd input/jd.txt \
  --name "Your Name" \
  --out output/tailored.docx

# LLM-based (recommended, requires OpenAI key)
python tailor.py \
  --resume input/resume.txt \
  --jd input/jd.txt \
  --name "Your Name" \
  --company "Google" \
  --role "ML Engineer" \
  --use-llm \
  --out output/tailored.docx
```

### C. Generate Cover Letter

```bash
# Update config.json with cover_letter block:
# {
#   "cover_letter": {
#     "resume": "input/resume.txt",
#     "jd": "input/jd.txt",
#     "name": "Your Name",
#     "company": "Google",
#     "role": "ML Engineer",
#     "out": "output/cover_letter.docx"
#   },
#   "openai": {
#     "enabled": true,
#     "model": "gpt-4o-mini"
#   }
# }

python cover_letter.py --config config.json
```

## 5. Essential Config Settings

Edit `config.json`:

```json
{
  "resume": "input/resume.txt",
  "top": 15,
  "openai": {
    "enabled": true,
    "model": "gpt-4o-mini"
  },
  "auto_tailor_resume": true,
  "tailor_threshold": 40,
  "use_job_app_generator": true,
  "free_options": {
    "mode": "free",
    "source": "remoteok",
    "query": "Python Engineer"
  },
  "output": {
    "dir": "output",
    "prefix": "matches"
  }
}
```

**Key settings:**
- `auto_tailor_resume: true` - Auto-generate tailored resumes for high-scoring jobs
- `tailor_threshold: 40` - Minimum score to trigger tailoring
- `use_job_app_generator: true` - Use unified LLM pipeline (recommended)
- `free_options.source` - Job board: `remoteok`, `remotive`, or `arbeitnow`
- `free_options.query` - Search keywords

## 6. Check Results

```bash
ls -lh output/

# You should see:
# - matched_jobs_*.json
# - matched_jobs_*.csv
# - cover_letters/cover_*.txt
# - tailored_resumes/resume_*.txt (if auto_tailor_resume: true)
```

## Common Issues

### "No module named 'langchain_core'"
```bash
# Make sure venv is activated and deps installed
source .venv/bin/activate
pip install -r requirements.txt
```

### "OPENAI_API_KEY not found"
```bash
# Check if .env file exists
cat .env

# Or export directly
export OPENAI_API_KEY=your_key
```

### "Resume file not found"
```bash
# Create input directory and add resume
mkdir -p input
echo "Your resume text" > input/resume.txt
```

## What's Next?

- **Schedule daily job matching**: See README.md for cron setup
- **Customize prompts**: Edit adapter files in `llm_*` modules
- **Add more job sources**: Update `selenium_options` in config
- **Batch processing**: Run `match.py` regularly for continuous job discovery

## Full Documentation

See `README.md` for complete feature list, configuration options, and troubleshooting.

## Need Help?

1. Check `README.md` - comprehensive guide
2. Review `CHANGES.md` - recent improvements
3. Look at `config.json` - example configuration
4. Read inline comments in Python files

---

**Pro Tip**: Start with `match.py` using default config, then customize based on results!


