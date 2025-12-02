# 🚀 Quick Apply Tool - User Guide

Generate tailored resume, cover letter, and match score from any job link or description in seconds!

## ✨ Features

- ✅ **Instant Resume Generation** - Tailored to specific job requirements
- ✅ **Automatic Cover Letter** - Personalized for each application
- ✅ **Match Score** - See how well you fit (0-100%)
- ✅ **Multiple Formats** - PDF and DOCX for both documents
- ✅ **Smart Detection** - Auto-extracts company name and job title
- ✅ **Supports All Job Boards** - Greenhouse, Lever, LinkedIn, Google Careers, and more

## 📋 Prerequisites

1. **Resume File**: Your resume in YAML format (`input/resume.yml`)
2. **Configuration**: Properly configured `config.json` with API keys
3. **Dependencies**: All Python packages installed (`pip install -r requirements.txt`)

## 🎯 Quick Start

### Option 1: From Job Link (Most Common)

```bash
python3 quick_apply.py --job-link "https://boards.greenhouse.io/stripe/jobs/5678910"
```

### Option 2: From Job Description Text

```bash
python3 quick_apply.py --job-description "We are looking for a Senior ML Engineer with 5+ years of experience in Python, TensorFlow, and AWS..."
```

### Option 3: From Job Description File

```bash
# Save job description to a file first
python3 quick_apply.py --jd-file "job_description.txt"
```

## 📖 Detailed Usage

### Basic Command Structure

```bash
python3 quick_apply.py [SOURCE] [OPTIONS]
```

### Source Options (Choose ONE)

| Option | Description | Example |
|--------|-------------|---------|
| `--job-link`, `--url` | Job posting URL | `--job-link "https://..."` |
| `--job-description`, `--jd` | Inline job description | `--jd "Software Engineer..."` |
| `--jd-file`, `--file` | File with job description | `--jd-file "job.txt"` |

### Optional Parameters

| Option | Description | Default |
|--------|-------------|---------|
| `--company`, `-c` | Override company name | Auto-detected |
| `--title`, `-t` | Override job title | Auto-detected |
| `--output`, `-o` | Output directory | `output/quick_apply` |
| `--resume`, `-r` | Resume YAML file | `input/resume.yml` |
| `--no-prompt` | Don't ask for missing info | Prompts by default |

## 💡 Examples

### Example 1: Simple Job Link
```bash
python3 quick_apply.py --job-link "https://boards.greenhouse.io/figma/jobs/123456"
```

**Output:**
```
🚀 Quick Apply Tool - Resume & Cover Letter Generator
======================================================================

📋 Loading resume from: input/resume.yml
✅ Resume loaded

🔍 Fetching job description from: https://boards.greenhouse.io/figma/jobs/123456
✅ Fetched 4,250 characters

🎯 Target Position:
   Company: Figma
   Title: Senior Software Engineer

🤖 Generating tailored resume and cover letter...
  📄 Generating resume content...
  💌 Generating cover letter content...
  📑 Generating resume PDF...
  📑 Generating resume DOCX...
  💌 Generating cover letter PDF...
  💌 Generating cover letter DOCX...

📊 Calculating match score...

======================================================================
✅ SUCCESS! Documents Generated
======================================================================

📌 Job Details:
   Company: Figma
   Position: Senior Software Engineer

📊 Match Score: 78.5%
   🟢 Excellent Match!

📄 Generated Files:
   Resume (PDF):  output/quick_apply/Figma_Senior_Software_Engineer_resume.pdf
   Resume (DOCX): output/quick_apply/Figma_Senior_Software_Engineer_resume.docx
   Cover Letter (PDF):  output/quick_apply/Figma_Senior_Software_Engineer_cover_letter.pdf
   Cover Letter (DOCX): output/quick_apply/Figma_Senior_Software_Engineer_cover_letter.docx

======================================================================
```

### Example 2: Manual Company and Title
```bash
python3 quick_apply.py \
  --job-link "https://example.com/careers/job/12345" \
  --company "Google" \
  --title "ML Engineer"
```

### Example 3: Custom Output Directory
```bash
python3 quick_apply.py \
  --job-link "https://jobs.lever.co/stripe/position-id" \
  --output "applications/stripe"
```

### Example 4: From Job Description File
```bash
# Create a file with job description
cat > google_ml_job.txt << EOF
Google is seeking a Machine Learning Engineer to join our AI team.
Requirements:
- 5+ years of experience in Python and TensorFlow
- Experience with large-scale ML systems
- Strong background in deep learning and NLP
EOF

# Generate documents
python3 quick_apply.py --jd-file "google_ml_job.txt" --company "Google" --title "ML Engineer"
```

### Example 5: No-Prompt Mode (Automated)
```bash
# Use this in scripts or CI/CD
python3 quick_apply.py \
  --job-link "https://..." \
  --company "Microsoft" \
  --title "Senior SWE" \
  --no-prompt
```

## 📊 Match Score Interpretation

| Score Range | Meaning | Color |
|-------------|---------|-------|
| 70-100% | 🟢 Excellent Match | Strong fit, high application priority |
| 50-69% | 🟡 Good Match | Solid candidate, worth applying |
| 30-49% | 🟠 Moderate Match | Consider if interested in company |
| 0-29% | 🔴 Weak Match | May need more relevant experience |

## 📁 Output Files

For each job, you'll get **4 files**:

```
output/quick_apply/
├── CompanyName_JobTitle_resume.pdf          # Main resume (for online upload)
├── CompanyName_JobTitle_resume.docx         # Editable resume (for customization)
├── CompanyName_JobTitle_cover_letter.pdf    # Main cover letter
└── CompanyName_JobTitle_cover_letter.docx   # Editable cover letter
```

## 🌐 Supported Job Boards

The tool automatically detects and extracts job information from:

- ✅ **Greenhouse** (`boards.greenhouse.io`)
- ✅ **Lever** (`jobs.lever.co`)
- ✅ **LinkedIn Jobs** (`linkedin.com/jobs`)
- ✅ **Google Careers** (`careers.google.com`)
- ✅ **Workday** (various company Workday portals)
- ✅ **Custom Career Pages** (company-specific job boards)
- ✅ **Any URL** (if job description is accessible)

## 🔧 Troubleshooting

### Problem: "Failed to fetch job description from URL"

**Solution:**
- Check if the URL is accessible in your browser
- Some job boards block automated access
- Use `--jd-file` option: copy job description to a text file

### Problem: "config.json not found"

**Solution:**
```bash
# Make sure you're in the correct directory
cd /Users/bhavananare/github/webapp/resume_py-master
python3 quick_apply.py --job-link "..."
```

### Problem: "Failed to generate resume"

**Solution:**
- Check if API keys are configured in `config.json`
- Verify LLM provider is enabled (Gemini/OpenAI/Ollama)
- Check environment variables: `GEMINI_API_KEY` or `OPENAI_API_KEY`

### Problem: Company/Title not detected

**Solution:**
```bash
# Manually specify them
python3 quick_apply.py \
  --job-link "..." \
  --company "Stripe" \
  --title "Backend Engineer"
```

## 🚀 Advanced Usage

### Batch Processing Multiple Jobs

```bash
#!/bin/bash
# Create a file with job links, one per line
cat > jobs.txt << EOF
https://boards.greenhouse.io/stripe/jobs/123
https://jobs.lever.co/figma/job-456
https://careers.google.com/jobs/789
EOF

# Process each job
while read job_url; do
  echo "Processing: $job_url"
  python3 quick_apply.py --job-link "$job_url" --no-prompt
  echo "---"
done < jobs.txt
```

### Using with Job Matcher Workflow

```bash
# First, run job matcher to find top matches
python3 match.py

# Check the output CSV
cat output/matches_daily_*.csv

# For each interesting job, generate tailored documents
python3 quick_apply.py --job-link "https://..."
```

### Integration with GitHub Actions

```yaml
# .github/workflows/quick-apply.yml
name: Quick Apply
on:
  workflow_dispatch:
    inputs:
      job_url:
        description: 'Job posting URL'
        required: true

jobs:
  apply:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Generate Documents
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: |
          python3 quick_apply.py \
            --job-link "${{ github.event.inputs.job_url }}" \
            --no-prompt
      - name: Upload artifacts
        uses: actions/upload-artifact@v3
        with:
          name: application-documents
          path: output/quick_apply/
```

## 📝 Tips for Best Results

1. **Keep Resume Updated**: Regularly update `input/resume.yml` with latest experience
2. **Review Match Score**: Focus on jobs with 50%+ match score
3. **Customize Further**: Use DOCX files to make manual adjustments if needed
4. **Save Job Links**: Keep a list of interesting job URLs for batch processing
5. **Check Output**: Always review generated documents before submitting

## 🆚 Quick Apply vs Full Job Matcher

| Feature | Quick Apply | Job Matcher |
|---------|-------------|-------------|
| **Use Case** | Single job application | Bulk job discovery |
| **Input** | Job link or description | Company lists, Selenium scraping |
| **Output** | Resume + Cover Letter + Score | CSV with top matches |
| **Speed** | 30-60 seconds | 5-30 minutes |
| **Best For** | Known job openings | Finding new opportunities |

## 📚 Related Commands

```bash
# Run full job matcher pipeline
python3 match.py

# Generate resume only (no cover letter)
python3 tailor.py --jd input/jd.txt --out output/resume.pdf

# View match history
cat output/matches_daily_*.csv | column -t -s,
```

## 💬 Support

If you encounter issues:

1. Check configuration: `cat config.json | grep -A 5 "openai\|gemini"`
2. Verify API keys: `echo $GEMINI_API_KEY`
3. Test LLM: `python3 -c "from llm_manager import LLMManager; print('OK')"`
4. Check logs: `cat execution.log | tail -50`

---

**Happy Applying! 🎉**

For more information, see the main README or reach out to the team.

