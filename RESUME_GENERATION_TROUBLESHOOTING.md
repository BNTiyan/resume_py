# Resume Generation Troubleshooting Guide

## Problem: "Score is More but Still Not Creating Resumes"

You're seeing high-scoring jobs (score 80+, 90+, 100+) but very few resumes are being created.

### Root Cause: Multiple Filters

The system applies **5 filtering stages**:

```
100 Jobs Fetched
    ↓
1️⃣  Score Filter (>= 40) → 65 jobs pass
    ↓
2️⃣  Sponsorship Check (disabled by default) → 60 jobs pass
    ↓
3️⃣  Role Match (14 target roles) → 45 jobs pass
    ↓
4️⃣  Per-Company Limit (1 per company) → 8 jobs max (1 per company)
    ↓
5️⃣  Description Available → 3-5 jobs with full descriptions
    ↓
3 Resumes Created ❌
```

---

## Why You See High Scores But Few Resumes

### Reason 1: `top_per_company_limit: 1`
```json
"top_per_company_limit": 1
```
- You have **8 companies**
- Only **1 job per company** can pass through
- **Maximum 8 resumes possible** (8 × 1)

**Fix: Increase to 2-3**
```json
"top_per_company_limit": 2  // Max 16 resumes (8 × 2)
```

---

### Reason 2: Sponsorship Check (Newly Added)
The sponsorship filter **blocks jobs that say**:
- ❌ "Visa sponsorship not available"
- ❌ "Requires US citizen/green card only"
- ❌ "No work permit sponsorship"

**Status: DISABLED by default** (but was enabled before)

To disable it (recommended for now):
```python
# Line 1249 in match.py:
has_sponsorship = check_sponsorship_available(jd_text, check_enabled=False)  # Disabled ✅
```

---

### Reason 3: Target Roles Too Specific
You have **14 very specific target roles**:
```json
"target_roles": [
  "software engineer",
  "senior software engineer",
  "principal software engineer",
  "staff software engineer",
  "machine learning engineer",
  "ml engineer",
  "mlops engineer",
  "data engineer",
  "backend engineer",
  "full stack engineer",
  "cloud engineer",
  "devops engineer",
  "site reliability engineer",
  "cybersecurity engineer"
]
```

Jobs that don't exactly match these are **skipped**.

**Fix: Remove or loosen filtering**
```json
"target_roles": []  // Empty = all roles accepted
```

---

### Reason 4: min_score Too High
```json
"min_score": 40
```
- Jobs scoring below 40 are filtered out
- If most jobs are 35-38, they get removed

**Fix: Lower threshold**
```json
"min_score": 30  // More jobs pass
```

---

### Reason 5: No Job Description
Jobs without descriptions cannot generate tailored resumes (even with high scores).

If JD is too short (< 50 chars), a minimal description is created, but LLM generation may skip it.

---

## Solution: Recommended Configuration

To get **16 resumes** instead of 3:

```json
{
  "min_score": 35,                   // ⬇️ Lower threshold
  "tailor_threshold": 35,            // ⬇️ Lower threshold
  "top_per_company_limit": 2,        // ⬆️ 2 jobs per company
  "target_roles": [],                // ✅ Accept all roles
  "target_locations": [],            // ✅ All locations
  
  // Keep these:
  "fetch_limit": 100,
  "companies": ["uber", "apple", "meta", "google", "amazon", "microsoft", "netflix", "oracle"],
  "selenium_only": true
}
```

**Expected results:**
- 8 companies × 2 jobs = **16 resumes maximum**
- With filtering: **12-14 actual resumes**

---

## How to Debug

Run with detailed logging enabled:

```bash
python match.py --config config.json 2>&1 | tee debug.log
```

Then check the **FILTERING SUMMARY** at the end:

```
================================================================================
📊 JOB FILTERING & RESUME GENERATION SUMMARY
================================================================================

🔍 FILTERING STAGES:
  1️⃣  Total jobs fetched: 100
  2️⃣  After score filter (>= 40): 65
  3️⃣  Sponsorship check:
       - Blocked (no sponsorship): 0
       - Passed sponsorship: 65
  4️⃣  Resumes created: 3

⚙️  CONFIG SETTINGS:
  - min_score: 40
  - tailor_threshold: 40
  - top_per_company_limit: 1
  - max possible resumes: 8 companies × 1 = 8
  - companies: 8 (uber, apple, meta, google, amazon...)
  - target_roles: 14 (software engineer, senior software engineer...)
================================================================================
```

**Key metrics:**
- `After score filter` = How many passed score threshold
- `Passed sponsorship` = How many didn't get blocked by sponsorship filter
- `Resumes created` = Actual resumes generated

---

## Step-by-Step Fix

### Step 1: Disable Sponsorship Check (if causing issues)
```python
# Line 1249 in match.py:
has_sponsorship = check_sponsorship_available(jd_text, check_enabled=False)
```

### Step 2: Update config.json
```json
{
  "min_score": 35,
  "tailor_threshold": 35,
  "top_per_company_limit": 2,
  "target_roles": []
}
```

### Step 3: Run again
```bash
python match.py --config config.json
```

### Step 4: Check summary
Look at the **FILTERING SUMMARY** to see exactly which filters are removing jobs.

---

## Common Scenarios

### Scenario A: Score is high (80+) but resume not created
**Likely reasons:**
1. `top_per_company_limit: 1` and company already used
2. Job description is too short
3. Role doesn't match target roles

**Fix:** Check logs for `[skip]` messages

### Scenario B: 100 jobs fetched but only 3 created
**Likely reasons:**
1. Most jobs don't match target roles
2. Most jobs don't have proper descriptions
3. Sponsorship check blocking jobs

**Fix:** 
- Set `target_roles: []` (accept all)
- Lower `min_score`
- Verify sponsorship check is disabled

### Scenario C: High score but low resume count
**Likely reasons:**
1. `top_per_company_limit: 1` is too restrictive
2. Only 1-2 companies have matching jobs

**Fix:** Increase `top_per_company_limit` to 2-3

---

## Configuration Presets

### Conservative (8 resumes max)
```json
{
  "min_score": 40,
  "tailor_threshold": 40,
  "top_per_company_limit": 1,
  "target_roles": [your 14 specific roles]
}
```

### Balanced (16 resumes max)
```json
{
  "min_score": 35,
  "tailor_threshold": 35,
  "top_per_company_limit": 2,
  "target_roles": []
}
```

### Aggressive (24 resumes max)
```json
{
  "min_score": 30,
  "tailor_threshold": 30,
  "top_per_company_limit": 3,
  "target_roles": []
}
```

---

## Quick Checklist

- [ ] Check `top_per_company_limit` value (1, 2, or 3?)
- [ ] Check `min_score` value (too high = fewer jobs pass)
- [ ] Check `tailor_threshold` (should match or be lower than min_score)
- [ ] Verify `target_roles` is not too restrictive (empty = all roles)
- [ ] Confirm sponsorship check is disabled (`check_enabled=False`)
- [ ] Check if jobs have descriptions (jobs without JD are skipped)
- [ ] Review FILTERING SUMMARY to see where jobs are being removed

---

## Next Run Command

```bash
# Update config with higher limits
python match.py --config config.json

# Or use fast config (if exists)
python match.py --config config.fast.json
```

**Expected improvement: 3 resumes → 12+ resumes ✅**

