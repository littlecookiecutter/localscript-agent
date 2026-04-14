"""Lua code generator agent using Ollama."""

import logging
import os
import re
import sys

import requests

# Setup path for imports
sys.path.append(os.path.dirname(os.path.abspath(os.path.join(__file__, '..'))))

from validator.checker import validate_lua

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a Lua code generator for a LowCode platform. Follow these rules strictly:

1. Use Lua 5.5 syntax.
2. Output format MUST be strictly: lua{your_code_here}lua
3. Variables must ONLY be accessed via wf.vars or wf.initVariables.
4. For arrays, you MUST use _utils.array.new() and _utils.array.markAsArray().
5. JsonPath is FORBIDDEN. Use direct property access only.
6. Allowed control structures: if, while, for, repeat. No other complex constructs.
7. Always end your code with a 'return' statement.
8. Do not include any explanations outside the lua{}lua block.

Generate clean, valid Lua code based on the user's request."""


class LuaAgent:
    """Agent that generates Lua code using Ollama LLM."""

    def __init__(self):
        self.base_url = "http://localhost:11434/api/generate"
        self.model = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b-instruct-q4_k_m")

    def _extract_code(self, text: str) -> str | None:
        """
        Extract Lua code from generated text.
        
        Looks for lua{...}lua or ```lua ... ``` patterns.
        Returns None if no pattern found.
        """
        # Pattern 1: lua{...}lua
        match = re.search(r'lua\{(.*?)\}lua', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        # Pattern 2: ```lua ... ```
        match = re.search(r'```lua\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        
        return None

    def _build_payload(self, prompt: str) -> dict:
        """Build the payload for Ollama API."""
        full_prompt = f"{SYSTEM_PROMPT}\n\nUser request: {prompt}"
        
        return {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "num_ctx": 4096,
                "num_predict": 256,
                "batch": 1,
                "parallel": 1
            }
        }

    def _call_ollama(self, payload: dict) -> str:
        """Make HTTP request to Ollama API."""
        try:
            response = requests.post(
                self.base_url,
                json=payload,
                timeout=60
            )
            
            # Handle HTTP 5xx errors
            if response.status_code >= 500:
                raise requests.HTTPError(f"Server error: {response.status_code}")
            
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
            
        except (requests.ConnectionError, requests.Timeout) as e:
            logger.error(f"Connection error or timeout: {e}")
            raise
        except requests.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            raise

    def generate(self, prompt: str, max_iterations: int = 2) -> dict:
        """
        Generate Lua code with validation loop.
        
        Args:
            prompt: User's request description
            max_iterations: Maximum number of generation attempts
            
        Returns:
            dict with keys: code, iterations, status, error
        """
        current_prompt = prompt
        last_error = None
        
        for iteration in range(1, max_iterations + 1):
            logger.info(f"Iteration {iteration}/{max_iterations}")
            
            try:
                # Build payload and call Ollama
                payload = self._build_payload(current_prompt)
                generated_text = self._call_ollama(payload)
                
                # Extract code
                code = self._extract_code(generated_text)
                
                if code is None:
                    last_error = "Failed to extract code from generated text"
                    if iteration < max_iterations:
                        current_prompt = f"Исправь код. Ошибки валидации: {last_error}. Исходный запрос: {prompt}"
                        continue
                    else:
                        return {
                            "code": None,
                            "iterations": iteration,
                            "status": "error",
                            "error": last_error
                        }
                
                # Validate code
                validation_result = validate_lua(code)
                
                if validation_result["valid"]:
                    return {
                        "code": code,
                        "iterations": iteration,
                        "status": "ok",
                        "error": None
                    }
                
                # Code is invalid
                errors = validation_result["errors"]
                last_error = "; ".join(errors) if errors else "Validation failed"
                
                if iteration < max_iterations:
                    # Prepare retry prompt with errors
                    current_prompt = f"Исправь код. Ошибки валидации: {last_error}. Исходный запрос: {prompt}"
                    logger.warning(f"Validation failed, retrying: {last_error}")
                else:
                    # Max iterations reached
                    return {
                        "code": code,
                        "iterations": iteration,
                        "status": "error",
                        "error": last_error
                    }
                    
            except (requests.ConnectionError, requests.Timeout) as e:
                return {
                    "code": None,
                    "iterations": iteration,
                    "status": "error",
                    "error": f"Connection error: {str(e)}"
                }
            except requests.HTTPError as e:
                status_code = e.response.status_code if e.response else "unknown"
                if status_code != "unknown" and status_code >= 500:
                    return {
                        "code": None,
                        "iterations": iteration,
                        "status": "error",
                        "error": f"Server error (HTTP {status_code})"
                    }
                return {
                    "code": None,
                    "iterations": iteration,
                    "status": "error",
                    "error": f"HTTP error: {str(e)}"
                }
            except Exception as e:
                return {
                    "code": None,
                    "iterations": iteration,
                    "status": "error",
                    "error": f"Unexpected error: {str(e)}"
                }
        
        # Should not reach here, but just in case
        return {
            "code": None,
            "iterations": max_iterations,
            "status": "error",
            "error": last_error or "Max iterations reached without success"
        }


if __name__ == "__main__":
    # Example usage
    agent = LuaAgent()
    
    test_prompt = "Create a function that doubles the input value from wf.vars"
    
    print(f"Generating code for: {test_prompt}")
    result = agent.generate(test_prompt, max_iterations=2)
    
    print(f"\nResult:")
    print(f"Status: {result['status']}")
    print(f"Iterations: {result['iterations']}")
    print(f"Error: {result['error']}")
    print(f"Code:\n{result['code']}")