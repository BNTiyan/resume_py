"""
LLM Manager - Supports multiple LLM providers
Default Priority: Gemini (free, cloud) > Ollama (free, local) > OpenAI (paid, disabled by default)
"""

import os
import sys
import time

# Determine which LLM to use based on environment
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'auto')  # 'auto', 'gemini', 'ollama', 'openai'
ENABLE_OPENAI = os.getenv('ENABLE_OPENAI', 'false').lower() == 'true'  # OpenAI disabled by default

class LLMManager:
    def __init__(self, config=None):
        """
        Optional config argument is accepted for backward compatibility with
        callers that pass a config object. Currently, provider selection is
        driven by environment variables, but we keep the config reference
        in case we want to read LLM-related settings from it in the future.
        """
        self.config = config or {}
        self.provider = None
        self.client = None
        self._initialize()
    
    def _initialize(self):
        """Initialize LLM provider based on priority/availability"""

        # Priority 1: Gemini (free, cloud, good quality)
        if LLM_PROVIDER in ['gemini', 'auto']:
            if self._try_gemini():
                return

        # Priority 2: HuggingFace Inference API (free tier, cloud, no local install)
        if LLM_PROVIDER in ['huggingface', 'hf', 'auto']:
            if self._try_huggingface():
                return

        # Priority 3: Ollama (free, local, unlimited)
        if LLM_PROVIDER in ['ollama', 'auto']:
            if self._try_ollama():
                return

        # Priority 4: OpenAI (paid, only if explicitly enabled)
        if LLM_PROVIDER == 'openai' or (LLM_PROVIDER == 'auto' and ENABLE_OPENAI):
            if self._try_openai():
                return
        
        print("\n" + "="*60)
        print("⚠️  No LLM provider available!")
        print("="*60)
        print("\n📋 Setup Instructions:\n")
        print("Option 1: Google Gemini (Recommended - FREE)")
        print("  1. Get API key: https://makersuite.google.com/app/apikey")
        print("  2. Set: export GEMINI_API_KEY='your_key_here'")
        print("  3. Free tier: 60 requests/minute\n")
        
        print("Option 2: Ollama (Free, Local, Unlimited)")
        print("  1. Install: curl -fsSL https://ollama.com/install.sh | sh")
        print("  2. Pull model: ollama pull llama3:8b")
        print("  3. Runs locally, no API key needed\n")
        
        print("Option 3: OpenAI (Paid - Disabled by default)")
        print("  1. Get API key: https://platform.openai.com/api-keys")
        print("  2. Set: export OPENAI_API_KEY='your_key_here'")
        print("  3. Enable: export ENABLE_OPENAI=true")
        print("  4. Cost: ~$0.10 per day for 5 applications\n")
        
        print("="*60 + "\n")
    
    def _try_gemini(self):
        """Try to use Google Gemini (cloud, free tier) - PRIORITY 1"""
        try:
            import google.generativeai as genai
            api_key = os.getenv('GEMINI_API_KEY')
            if api_key:
                genai.configure(api_key=api_key)
                # Use Gemini 2.0 Flash by default; allow override via GEMINI_MODEL
                model_name = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
                model = genai.GenerativeModel(model_name)
                self.client = model
                self.provider = 'gemini'
                print(f"✓ Using Google Gemini model: {model_name}")
                return True
        except Exception as e:
            if LLM_PROVIDER == 'gemini':
                print(f"✗ Gemini not available: {e}")
                print("  Get key: https://makersuite.google.com/app/apikey")
        return False
    
    def _try_huggingface(self):
        """Try to use HuggingFace Inference API (free tier, cloud) - PRIORITY 2"""
        hf_token = os.getenv('HUGGINGFACE_API_TOKEN') or os.getenv('HF_TOKEN')
        # HF Inference API works without a token for public models at low rate limits,
        # but a free token (https://huggingface.co/settings/tokens) gives higher limits.
        try:
            import requests as _req
            model = os.getenv('HF_MODEL', 'mistralai/Mistral-7B-Instruct-v0.3')
            headers = {"Authorization": f"Bearer {hf_token}"} if hf_token else {}
            # Quick probe — check the model info endpoint (no tokens consumed)
            r = _req.get(
                f"https://api-inference.huggingface.co/models/{model}",
                headers=headers, timeout=5
            )
            if r.status_code in (200, 503):  # 503 = model loading, still valid
                self.client = {"hf_token": hf_token, "model": model}
                self.provider = 'huggingface'
                tier = "FREE (authenticated)" if hf_token else "FREE (anonymous, lower limits)"
                print(f"✓ Using HuggingFace Inference API ({model}) - {tier}")
                print("  Get a free token: https://huggingface.co/settings/tokens")
                return True
        except Exception as e:
            if LLM_PROVIDER in ('huggingface', 'hf'):
                print(f"✗ HuggingFace not available: {e}")
        return False

    def _try_ollama(self):
        """Try to use Ollama (local, free) - PRIORITY 3"""
        try:
            import requests
            # Check if Ollama is running
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            if response.status_code == 200:
                from ollama_adapter import get_ollama_client
                model = os.getenv('OLLAMA_MODEL', 'llama3:8b')
                self.client = get_ollama_client(model=model)
                self.provider = 'ollama'
                print(f"✓ Using Ollama ({model}) - FREE, LOCAL, UNLIMITED")
                return True
        except Exception as e:
            if LLM_PROVIDER == 'ollama':
                print(f"✗ Ollama not available: {e}")
                print("  Install: curl -fsSL https://ollama.com/install.sh | sh")
        return False
    
    def _try_openai(self):
        """Try to use OpenAI (paid) - PRIORITY 3, DISABLED BY DEFAULT"""
        if not ENABLE_OPENAI and LLM_PROVIDER == 'auto':
            # Silently skip OpenAI in auto mode if not explicitly enabled
            return False
        
        try:
            from openai import OpenAI
            api_key = os.getenv('OPENAI_API_KEY')
            if api_key:
                self.client = OpenAI(api_key=api_key)
                self.provider = 'openai'
                print("✓ Using OpenAI - PAID, LIMITED REQUESTS")
                print("  (Set ENABLE_OPENAI=false to disable)")
                return True
        except Exception as e:
            if LLM_PROVIDER == 'openai':
                print(f"✗ OpenAI not available: {e}")
                print("  Get key: https://platform.openai.com/api-keys")
        return False
    
    def generate(self, messages, temperature=0.7, max_tokens=6000, max_retries=3):
        """Generate response from LLM with retry logic for rate limits"""
        if not self.client:
            raise Exception("No LLM provider available")

        # Normalize input: allow both raw strings and OpenAI-style message lists
        if isinstance(messages, str):
            # Treat plain string as a single user message
            messages = [{"role": "user", "content": messages}]
        elif isinstance(messages, dict):
            # Single dict -> wrap in list
            messages = [messages]

        # Retry loop with exponential backoff
        for attempt in range(max_retries):
            try:
                # Primary generation path based on current provider
                if self.provider == 'ollama':
                    return self._generate_ollama(messages, temperature, max_tokens)
                elif self.provider == 'gemini':
                    return self._generate_gemini(messages, temperature, max_tokens)
                elif self.provider == 'openai':
                    return self._generate_openai(messages, temperature, max_tokens)
                elif self.provider == 'huggingface':
                    return self._generate_huggingface(messages, temperature, max_tokens)
                    
            except Exception as e:
                error_str = str(e).lower()
                
                # Check if it's a rate limit error
                is_rate_limit = any(phrase in error_str for phrase in [
                    'rate limit', 'quota', '429', 'too many requests', 
                    'resource_exhausted', 'resourceexhausted'
                ])
                
                if is_rate_limit and attempt < max_retries - 1:
                    # Exponential backoff: 2^attempt seconds (2s, 4s, 8s)
                    wait_time = 2 ** (attempt + 1)
                    print(f"⚠️  Rate limit hit on {self.provider}. Retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                    continue
                
                # If Gemini fails (rate limit exhausted or other error), try fallback
                if self.provider == 'gemini':
                    print(f"\n⚠️  Gemini failure: {e}")
                    if is_rate_limit:
                        print("   Gemini quota exhausted. Trying fallback providers...")
                    else:
                        print("   Attempting fallback to other providers...\n")

                    # Clear current client and try other providers
                    self.client = None
                    self.provider = None

                    # Try HF first (free, cloud), then Ollama (free, local), then OpenAI
                    if self._try_huggingface() or self._try_ollama() or self._try_openai():
                        # Recursive call will use the new provider
                        return self.generate(messages, temperature, max_tokens, max_retries)

                # If not Gemini, or no fallback succeeded, re-raise
                raise
        
        # If we exhausted all retries
        raise Exception(f"Failed to generate after {max_retries} attempts due to rate limits")
    
    def _generate_huggingface(self, messages, temperature, max_tokens):
        """Generate with HuggingFace Inference API (free tier)"""
        import requests as _req
        cfg = self.client  # {"hf_token": ..., "model": ...}
        model = cfg["model"]
        hf_token = cfg.get("hf_token")

        # Convert messages to a single prompt string (chat/instruct format)
        prompt = self._messages_to_prompt(messages)

        headers = {"Content-Type": "application/json"}
        if hf_token:
            headers["Authorization"] = f"Bearer {hf_token}"

        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": min(max_tokens, 2048),
                "temperature": max(temperature, 0.01),  # HF API disallows 0
                "return_full_text": False,
            },
        }
        url = f"https://api-inference.huggingface.co/models/{model}"
        response = _req.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list) and data:
            return data[0].get("generated_text", "").strip()
        raise Exception(f"Unexpected HF response: {data}")

    def _generate_ollama(self, messages, temperature, max_tokens):
        """Generate with Ollama"""
        response = self.client.chat_completions_create(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    
    def _generate_gemini(self, messages, temperature, max_tokens):
        """Generate with Gemini"""
        # Convert messages to Gemini format
        prompt = self._messages_to_prompt(messages)
        response = self.client.generate_content(
            prompt,
            generation_config={
                'temperature': temperature,
                'max_output_tokens': max_tokens
            }
        )
        return response.text
    
    def _generate_openai(self, messages, temperature, max_tokens):
        """Generate with OpenAI"""
        response = self.client.chat.completions.create(
            model=os.getenv('OPENAI_MODEL', 'gpt-4o-mini'),
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    
    def _messages_to_prompt(self, messages):
        """Convert OpenAI-style messages to single prompt"""
        prompt = ""
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                prompt += f"System Instructions: {content}\n\n"
            elif role == "user":
                prompt += f"User: {content}\n\n"
            elif role == "assistant":
                prompt += f"Assistant: {content}\n\n"
        
        return prompt.strip()


# Global instance
_llm_manager = None

def get_llm():
    """Get LLM manager instance"""
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = LLMManager()
    return _llm_manager


# For backward compatibility
def get_client():
    """Get underlying LLM client"""
    llm = get_llm()
    return llm.client if llm else None

