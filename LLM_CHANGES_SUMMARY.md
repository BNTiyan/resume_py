# ✅ LLM Configuration Complete!

## 🎯 What Changed

### Default Priority (NEW):
1. **Gemini** (Google) → FREE, tries first ✅
2. **Ollama** (Local) → FREE, tries second ✅
3. **OpenAI** → PAID, **DISABLED by default** ❌

### Old vs New

**Before:**
```
- OpenAI enabled by default (costs money)
- No fallback options
- Had to have OpenAI key to work
```

**After:**
```
✅ Gemini tries first (free, no installation)
✅ Ollama tries second (free, local)
❌ OpenAI disabled by default (must enable with ENABLE_OPENAI=true)
✅ Auto fallback between providers
✅ Clear setup instructions if none available
```

---

## 🚀 Quick Start (Choose One)

### Option 1: Gemini (Easiest - Recommended)

```bash
# 1. Get free API key
# Visit: https://makersuite.google.com/app/apikey

# 2. Set the key
export GEMINI_API_KEY="your_key_here"

# 3. Run the tool
cd /Users/bhavananare/github/webapp/resume_py-master
python agent_cli.py --config config.json

# ✓ Free: 60 requests/minute
# ✓ Good quality
# ✓ No installation needed
```

---

### Option 2: Ollama (Most Private)

```bash
# 1. Install Ollama (one-time)
curl -fsSL https://ollama.com/install.sh | sh

# 2. Download model (one-time, ~4GB)
ollama pull llama3:8b

# 3. Run the tool
cd /Users/bhavananare/github/webapp/resume_py-master
python agent_cli.py --config config.json

# ✓ 100% free forever
# ✓ Unlimited requests
# ✓ Works offline
# ✓ Data stays local
```

---

### Option 3: OpenAI (Best Quality, Paid)

```bash
# OpenAI is DISABLED by default to avoid costs
# To enable:

export ENABLE_OPENAI=true
export OPENAI_API_KEY="sk-proj-xxx"

python agent_cli.py --config config.json

# Cost: ~$0.10/day for 5 applications
```

---

## 🎮 How It Works

### Auto Mode (Default)

When you run the tool:

```
1. Checks for GEMINI_API_KEY
   ✓ Found? → Use Gemini (free)
   ✗ Not found? → Try next
   
2. Checks if Ollama is running
   ✓ Running? → Use Ollama (free, local)
   ✗ Not running? → Try next
   
3. Checks for OpenAI + ENABLE_OPENAI=true
   ✓ Both set? → Use OpenAI (paid)
   ✗ Not enabled? → Show setup instructions
```

### Force Specific Provider

```bash
# Force Gemini only
export LLM_PROVIDER=gemini
export GEMINI_API_KEY="your_key"

# Force Ollama only  
export LLM_PROVIDER=ollama

# Force OpenAI only
export LLM_PROVIDER=openai
export ENABLE_OPENAI=true
export OPENAI_API_KEY="sk-xxx"
```

---

## 💰 Cost Comparison

### For 5 Job Applications Per Day:

| Provider | Daily Cost | Monthly Cost | Rate Limit |
|----------|------------|--------------|------------|
| **Gemini** | $0 | $0 | 60/min |
| **Ollama** | $0 | $0 | Unlimited |
| **OpenAI** | ~$0.10 | ~$3 | 3/min |

**Recommendation:** Use **Gemini** (free + easy) or **Ollama** (free + private)

---

## 📁 Files Created/Modified

### New Files:
1. **`llm_manager.py`** - Smart LLM provider manager
2. **`ollama_adapter.py`** - Ollama compatibility adapter
3. **`LLM_SETUP_GUIDE.md`** - Detailed setup instructions

### Modified Files:
1. **`config.json`** - Set `openai.enabled: false`

---

## ✅ Verification

### Check which LLM will be used:

```bash
cd /Users/bhavananare/github/webapp/resume_py-master
python -c "from llm_manager import get_llm; get_llm()"
```

**Expected output:**
```
✓ Using Google Gemini - FREE TIER, 60 req/min, CLOUD
```

Or if Gemini not set:
```
✓ Using Ollama (llama3:8b) - FREE, LOCAL, UNLIMITED
```

Or if neither available:
```
⚠️  No LLM provider available!
[Shows setup instructions]
```

---

## 🎯 Next Steps

### 1. Set up Gemini (Recommended):
```bash
# Get key: https://makersuite.google.com/app/apikey
export GEMINI_API_KEY="your_key_here"
```

### 2. Run the tool:
```bash
python agent_cli.py --config config.json
```

### 3. Verify it works:
```
✓ Using Google Gemini - FREE TIER, 60 req/min, CLOUD
✓ Fetched 73 jobs from 25 companies
✓ Selected top 5 matches
✓ Generating tailored resumes...
✓ Resume 1/5 created
...
```

---

## 🆘 Troubleshooting

### "No LLM provider available"

**Quick fix:**
```bash
# Option 1: Use Gemini (2 min setup)
export GEMINI_API_KEY="your_key_from_makersuite.google.com"

# Option 2: Use Ollama (5 min setup)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3:8b
```

### "Rate limit exceeded" (Gemini)

Switch to Ollama (unlimited):
```bash
export LLM_PROVIDER=ollama
```

### "Want to use OpenAI"

Enable it explicitly:
```bash
export ENABLE_OPENAI=true
export OPENAI_API_KEY="sk-proj-xxx"
```

---

## 📊 Summary

**What you get:**
- ✅ OpenAI **disabled by default** (no surprise costs)
- ✅ Gemini **tries first** (free, easy)
- ✅ Ollama **tries second** (free, unlimited)
- ✅ Auto fallback if one fails
- ✅ Clear setup instructions
- ✅ Full control via environment variables

**Setup time:**
- Gemini: **2 minutes** (get API key)
- Ollama: **5 minutes** (install + download model)
- OpenAI: **2 minutes** (but costs money)

**Recommendation:** 
Start with **Gemini** (fastest setup, free, good quality) 🚀

---

## 🎉 You're All Set!

The tool now uses **free LLMs by default** with **OpenAI disabled** to avoid costs.

Just set up Gemini or Ollama and start applying to jobs! 🚀

```bash
export GEMINI_API_KEY="your_key_here"
python agent_cli.py --config config.json
```

