# Why Only 3 Resumes Were Created

## Current Configuration

```json
{
  "min_score": 40.0,                  // Minimum score to process jobs
  "tailor_threshold": 40,             // Score needed to create resume
  "top_per_company_limit": 1,         // Max 1 job per company
  "companies": 8,                     // [uber, apple, meta, google, amazon, microsoft, netflix, oracle]
  "fetch_limit": 100,                 // Fetch top 100 jobs
  "target_roles": 14,                 // Specific software engineering roles
  "target_locations": []              // All US locations
}
```

## Maximum Possible Resumes

With **8 companies × 1 job per company = maximum 8 resumes possible**

But you got **only 3 resumes**, which means **5 companies were filtered out**.

## Filtering Pipeline

### Stage 1: Score Filter
```
Total jobs fetched → Filter score >= 40.0 → X jobs pass
```

### Stage 2: Visa Sponsorship Filter ⭐ (NEWLY ADDED)
```
X jobs → Check for visa sponsorship text → Y jobs with sponsorship
```
**This is likely your main filter!** Jobs that say:
- ❌ "Visa sponsorship not available"
- ❌ "Requires US citizen/green card"
- ❌ "No work permit sponsorship"

These are **automatically skipped**.

### Stage 3: Target Role Filter
```
Y jobs → Match against 14 target roles → Z jobs match roles
```

### Stage 4: Per-Company Limit
```
Z jobs → Select top 1 per company → Final resumes
```

## Why Only 3?

**Most likely reasons:**

1. **Visa Sponsorship Filter Blocked 5 Companies**
   - Jobs from Uber, Apple, Meta, Amazon, or Microsoft/Netflix/Oracle said "no sponsorship"
   - These were skipped automatically

2. **Score Too Low**
   - Jobs from 5 companies scored below 40.0
   - They didn't pass the score filter

3. **No Matching Target Roles**
   - Jobs from 5 companies didn't match your target roles
   - You have very specific roles defined

4. **No Job Description**
   - 5 companies' jobs had empty or very short descriptions
   - System skipped them

5. **Combination of Above**
   - Each company had at least 1 filter applied

## How to Get More Resumes

### Option 1: Lower the Minimum Score
```json
"min_score": 30.0,           // Was 40.0
"tailor_threshold": 30       // Was 40
```

### Option 2: Allow Multiple Jobs Per Company
```json
"top_per_company_limit": 3   // Was 1 → Get up to 3 per company
```

### Option 3: Expand Target Roles
```json
"target_roles": [
  "software engineer",
  "senior software engineer",
  "machine learning engineer",
  "data engineer",
  "backend engineer",
  "any engineer"  // Add more generic roles
]
```

### Option 4: Review Sponsorship Filter
If the sponsorship filter is too aggressive, you can modify the patterns:

**File:** `match.py` (line 387-398)

```python
no_sponsorship_patterns = [
    r"visa\s+sponsorship\s+is\s+not\s+available",
    # ... add or remove patterns
]
```

## Debug Output

Next run will now show:

```
[check] ✅ SPONSORSHIP: Sponsorship available
  OR
[skip] ⏭️ ❌ SPONSORSHIP: No visa sponsorship available for this position
       Company: Google | Role: Software Engineer | Score: 85.2
```

And at the end:

```
================================================================================
📊 JOB FILTERING SUMMARY
================================================================================
Total jobs fetched: 100
After score filter (>= 40.0): 65
Jobs processed for resume generation: 3
Config settings:
  - min_score: 40.0
  - tailor_threshold: 40
  - top_per_company_limit: 1
  - companies: 8 (uber, apple, meta, google, amazon...)
  - target_roles: 14 (software engineer, senior software engineer...)
================================================================================
```

## Recommended Action

To get more resumes, try:

```json
{
  "min_score": 35.0,          // Lower threshold
  "tailor_threshold": 35,
  "top_per_company_limit": 2  // Allow 2 per company → up to 16 resumes
}
```

This would allow you to get up to **16 resumes** (8 companies × 2 jobs each) instead of 8.

## Running the Next Test

```bash
python match.py --config config.json
```

Check the logs for:
- `[skip] ⏭️ ❌ SPONSORSHIP:` → Shows which jobs were skipped for sponsorship
- `📊 JOB FILTERING SUMMARY` → Shows complete statistics

