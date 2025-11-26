# LLM Configuration Guide

## 🎯 Default Behavior

**Priority Order:**
1. **Gemini** (Google) - FREE, tries first
2. **Ollama** (Local) - FREE, tries second
3. **OpenAI** - PAID, **DISABLED by default**

## 🚀 Quick Start

### Option 1: Use Gemini (Recommended - Default)

```bash
# Get your free API key
# Visit: https://makersuite.google.com/app/apikey

# Set the key
export GEMINI_API_KEY="your_key_here"

# Run the tool (will automatically use Gemini)
python agent_cli.py --config config.json
```

**Benefits:**
- ✅ Free tier: 60 requests/minute
- ✅ No installation needed
- ✅ Good quality
- ✅ Works immediately

---

### Option 2: Use Ollama (Local, Unlimited)

```bash
# Install Ollama (one-time setup)
curl -fsSL https://ollama.com/install.sh | sh

# Download a model (one-time, ~4GB)
ollama pull llama3:8b

# Run the tool (will auto-detect Ollama if Gemini not available)
python agent_cli.py --config config.json
```

**Benefits:**
- ✅ 100% free forever
- ✅ Unlimited requests
- ✅ Works offline
- ✅ Fast
- ✅ Privacy (data stays local)

---

### Option 3: Use OpenAI (Paid - Must Enable)

```bash
# Get API key: https://platform.openai.com/api-keys

# Enable OpenAI (disabled by default)
export ENABLE_OPENAI=true
export OPENAI_API_KEY="sk-proj-xxx"

# Run the tool
python agent_cli.py --config config.json
```

**Note:** OpenAI is **disabled by default** to avoid unexpected costs.

---

## 🔧 Advanced Configuration

### Force Specific Provider

```bash
# Force Gemini only
export LLM_PROVIDER=gemini
python agent_cli.py --config config.json

# Force Ollama only
export LLM_PROVIDER=ollama
python agent_cli.py --config config.json

# Force OpenAI (must also set ENABLE_OPENAI=true)
export LLM_PROVIDER=openai
export ENABLE_OPENAI=true
python agent_cli.py --config config.json

# Auto mode (default: Gemini → Ollama → OpenAI if enabled)
export LLM_PROVIDER=auto  # or don't set it
python agent_cli.py --config config.json
```

### Disable OpenAI Completely

OpenAI is already disabled by default. To ensure it's never used:

```bash
export ENABLE_OPENAI=false
# or don't set it at all (false is default)
```

### Change Ollama Model

```bash
# Use different Ollama model
export OLLAMA_MODEL=mistral
# or
export OLLAMA_MODEL=codellama
# or
export OLLAMA_MODEL=llama3:70b  # larger, better quality

ollama pull $OLLAMA_MODEL  # download if not already
python agent_cli.py --config config.json
```

---

## 📊 Comparison

| Provider | Cost | Speed | Quality | Setup | Offline |
|----------|------|-------|---------|-------|---------|
| **Gemini** | Free | Fast | Very Good | Easy | No |
| **Ollama** | Free | Fast | Good | Medium | Yes |
| **OpenAI** | $0.10/day | Fast | Excellent | Easy | No |

### For Daily Use (5 job applications/day):

| Provider | Monthly Cost | Rate Limit | Recommended For |
|----------|--------------|------------|-----------------|
| **Gemini** | $0 | 60/min | Everyone (default) |
| **Ollama** | $0 | Unlimited | Privacy-conscious users |
| **OpenAI** | ~$3 | 3/min | Users wanting best quality |

---

## 🎯 Recommended Setup

### For Most Users:
```bash
# Just set Gemini key and you're done
export GEMINI_API_KEY="your_key_here"
python agent_cli.py --config config.json
```

### For Privacy/Offline:
```bash
# Install Ollama once
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3:8b

# Then use forever (no API key needed)
python agent_cli.py --config config.json
```

### For Best Quality (willing to pay):
```bash
# Enable OpenAI explicitly
export ENABLE_OPENAI=true
export OPENAI_API_KEY="sk-proj-xxx"
python agent_cli.py --config config.json
```

---

## 🐛 Troubleshooting

### "No LLM provider available"

**Solution 1:** Set up Gemini (easiest)
```bash
export GEMINI_API_KEY="your_key_here"
```
Get key: https://makersuite.google.com/app/apikey

**Solution 2:** Install Ollama
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3:8b
```

### "Gemini rate limit exceeded"

Switch to Ollama (unlimited):
```bash
export LLM_PROVIDER=ollama
```

Or use OpenAI:
```bash
export LLM_PROVIDER=openai
export ENABLE_OPENAI=true
```

### "Ollama connection refused"

Make sure Ollama is running:
```bash
ollama serve  # start Ollama server
# In another terminal:
python agent_cli.py --config config.json
```

Or fall back to Gemini:
```bash
export LLM_PROVIDER=gemini
export GEMINI_API_KEY="your_key"
```

### "OpenAI not being used"

OpenAI is disabled by default. Enable it:
```bash
export ENABLE_OPENAI=true
export OPENAI_API_KEY="sk-proj-xxx"
```

---

## 📝 Environment Variables Summary

| Variable | Default | Options | Description |
|----------|---------|---------|-------------|
| `LLM_PROVIDER` | `auto` | `auto`, `gemini`, `ollama`, `openai` | Which LLM to use |
| `ENABLE_OPENAI` | `false` | `true`, `false` | Enable paid OpenAI API |
| `GEMINI_API_KEY` | - | Your API key | Google Gemini API key |
| `OPENAI_API_KEY` | - | Your API key | OpenAI API key |
| `OLLAMA_MODEL` | `llama3:8b` | Any Ollama model | Which Ollama model |

---

## 🎉 Quick Commands

### Check what LLM will be used:
```bash
python -c "from llm_manager import get_llm; get_llm()"
```

### Test Gemini:
```bash
export GEMINI_API_KEY="your_key"
python -c "from llm_manager import get_llm; llm=get_llm(); print(llm.provider)"
```

### Test Ollama:
```bash
ollama pull llama3:8b
python -c "from llm_manager import get_llm; llm=get_llm(); print(llm.provider)"
```

---

## ✅ Recommended: Use Gemini

**Why Gemini is the default:**
- ✅ Free (60 requests/minute)
- ✅ No installation required
- ✅ Very good quality
- ✅ Easy setup (just get API key)
- ✅ Works immediately

**Setup in 2 minutes:**
1. Visit https://makersuite.google.com/app/apikey
2. Click "Create API key"
3. Copy the key
4. `export GEMINI_API_KEY="your_key"`
5. Run the tool!

**That's it!** 🚀

