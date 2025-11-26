# Ollama Adapter for Resume Tool
# Drop-in replacement for OpenAI API

import requests
import json

class OllamaClient:
    def __init__(self, base_url="http://localhost:11434", model="llama3:8b"):
        self.base_url = base_url
        self.model = model
    
    def chat_completions_create(self, messages, **kwargs):
        """OpenAI-compatible interface"""
        # Convert OpenAI format to Ollama format
        prompt = self._messages_to_prompt(messages)
        
        response = requests.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": kwargs.get("temperature", 0.7),
                    "num_predict": kwargs.get("max_tokens", 2000)
                }
            }
        )
        
        result = response.json()
        
        # Return in OpenAI format
        return type('obj', (object,), {
            'choices': [
                type('obj', (object,), {
                    'message': type('obj', (object,), {
                        'content': result['response']
                    })()
                })()
            ]
        })()
    
    def _messages_to_prompt(self, messages):
        """Convert OpenAI messages to single prompt"""
        prompt = ""
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                prompt += f"System: {content}\n\n"
            elif role == "user":
                prompt += f"User: {content}\n\n"
            elif role == "assistant":
                prompt += f"Assistant: {content}\n\n"
        
        prompt += "Assistant: "
        return prompt


# Singleton instance
_ollama_client = None

def get_ollama_client(model="llama3:8b"):
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OllamaClient(model=model)
    return _ollama_client

