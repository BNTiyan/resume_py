
import os
import sys
import json
from dotenv import load_dotenv
from llm_manager import LLMManager

load_dotenv()

print(f"Python executable: {sys.executable}")

def load_config():
    try:
        with open("config.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def test_llm():
    print("Initializing LLMManager...")
    config = load_config()
    # verify we have gemini config
    if config.get('gemini'):
        print(f"Found Gemini config: {config.get('gemini').get('model')}")
        # Manually set env var if needed or just pass config
        if config.get('gemini').get('api_key'):
             key = config.get('gemini').get('api_key')
             print(f"API Key present: {key[:4]}...{key[-4:] if len(key)>8 else ''}")
             os.environ['GEMINI_API_KEY'] = key
        else:
             print("API Key NOT found in config['gemini']['api_key']")
    
    # Re-initialize manager with config to be sure
    llm = LLMManager(config=config)
    print(f"Provider: {llm.provider}")
    
    if llm.client:
        print("Client initialized successfully.")
        try:
            print("Generating text...")
            response = llm.generate("Hello, are you working?", max_tokens=50)
            print(f"Response: {response}")
        except Exception as e:
            print(f"Generation failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("Client NOT initialized.")

if __name__ == "__main__":
    test_llm()
