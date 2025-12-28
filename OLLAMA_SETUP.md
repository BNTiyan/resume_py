# Ollama Setup Guide - Unlimited Local LLM

## Why Ollama?

**Ollama provides unlimited, FREE resume generation** that runs locally on your machine. No API keys, no rate limits, no quota exhaustion!

## Benefits

- ✅ **Unlimited requests** - Generate as many resumes as you want
- ✅ **No API costs** - Completely free forever
- ✅ **Privacy** - Your data never leaves your machine
- ✅ **Fast** - No network latency, runs locally
- ✅ **Automatic fallback** - The system automatically uses Ollama when Gemini hits rate limits

## Installation

### macOS / Linux
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Windows
Download installer from: https://ollama.com/download

## Setup (One-time)

1. **Pull a model** (recommended: llama3:8b - good quality, reasonable size)
```bash
ollama pull llama3:8b
```

2. **Verify it's running**
```bash
ollama list
```

You should see `llama3:8b` listed.

## That's It!

Your system will automatically:
1. Try Gemini first (fast, cloud-based)
2. If Gemini hits rate limits → automatically retry with exponential backoff
3. If Gemini quota exhausted → automatically fall back to Ollama (unlimited)
4. Continue generating resumes without interruption

## Customization

### Use a different model
```bash
# Smaller, faster model (lower quality)
ollama pull llama3:8b

# Larger, higher quality model (slower)
ollama pull llama3:70b

# Set your preferred model
export OLLAMA_MODEL=llama3:70b
```

### Check if Ollama is running
```bash
curl http://localhost:11434/api/tags
```

If you get a response, Ollama is running and ready to use!

## Troubleshooting

**Problem:** "Ollama not available"
**Solution:** Make sure Ollama is installed and running:
```bash
ollama serve  # Start Ollama server if not running
```

**Problem:** "Model not found"
**Solution:** Pull the model first:
```bash
ollama pull llama3:8b
```

## Resource Usage

- **RAM needed**: ~8GB for llama3:8b, ~64GB for llama3:70b
- **Disk space**: ~4.7GB for llama3:8b, ~40GB for llama3:70b
- **CPU/GPU**: Works on CPU, GPU acceleration available if you have a compatible GPU

---

With Ollama installed, you'll **never hit rate limits again**!
