"""
Lua Code Generator Agent using Ollama API.

This module provides a LuaAgent class that generates Lua code via local Ollama API.
"""

import json
import re
import time
from typing import Optional, Dict, Any

try:
    import requests
except ImportError:
    raise ImportError("Please install 'requests' package: pip install requests")


class LuaAgent:
    """
    Agent for generating Lua code using Ollama API.
    
    Attributes:
        base_url: Ollama API base URL (default: http://localhost:11434)
        model: Model name to use for generation
        timeout: Request timeout in seconds
    """
    
    DEFAULT_MODEL = "qwen2.5-coder:7b-instruct-q4_k_m"
    DEFAULT_BASE_URL = "http://localhost:11434"
    DEFAULT_TIMEOUT = 60
    
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout: int = DEFAULT_TIMEOUT
    ):
        """
        Initialize the LuaAgent.
        
        Args:
            base_url: Ollama API base URL
            model: Model name for code generation
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
    
    def _build_system_prompt(self) -> str:
        """
        Build the system prompt for Lua code generation.
        
        Returns:
            System prompt string with Lua coding guidelines.
        """
        return """You are an expert Lua 5.5 developer. Your task is to generate clean, efficient Lua code.

IMPORTANT RULES:
1. All code must be written in Lua 5.5 syntax.
2. All variables must be stored in wf.vars or wf.initVariables.
   - Use wf.vars.variableName for existing variables
   - Use wf.initVariables.variableName for new variable initialization
3. For arrays, always use:
   - _utils.array.new() to create new arrays
   - _utils.array.markAsArray() to mark tables as arrays
4. Do not use global variables outside of wf.vars or wf.initVariables.
5. Follow Lua best practices and write readable code.

OUTPUT FORMAT:
Your response MUST contain the generated code wrapped in this exact format:
{"result":"lua{...your lua code here...}lua"}

The code between lua{ and }lua should be valid Lua code only, without any markdown formatting.
Do not include explanations outside of this format."""

    def _extract_code_from_response(self, response_text: str) -> Optional[str]:
        """
        Extract Lua code from the model's response.
        
        Args:
            response_text: Raw response text from the model
            
        Returns:
            Extracted Lua code or None if extraction fails
        """
        # Pattern to match {"result":"lua{...}lua"}
        pattern = r'\{"result"\s*:\s*"lua\{(.+?)\}lua"'
        
        match = re.search(pattern, response_text, re.DOTALL)
        if match:
            code = match.group(1).strip()
            # Unescape any JSON-escaped characters
            code = code.replace('\\"', '"').replace('\\n', '\n')
            code = code.replace('\\\\', '\\')
            return code
        
        # Fallback: try to find lua{...}lua pattern without JSON wrapper
        fallback_pattern = r'lua\{(.+?)\}lua'
        fallback_match = re.search(fallback_pattern, response_text, re.DOTALL)
        if fallback_match:
            code = fallback_match.group(1).strip()
            code = code.replace('\\"', '"').replace('\\n', '\n')
            code = code.replace('\\\\', '\\')
            return code
        
        return None

    def _call_ollama(
        self,
        prompt: str,
        system_prompt: str,
        num_ctx: int = 4096,
        num_predict: int = 256
    ) -> str:
        """
        Call Ollama API to generate code.
        
        Args:
            prompt: User prompt for code generation
            system_prompt: System prompt with guidelines
            num_ctx: Context window size
            num_predict: Maximum tokens to predict
            
        Returns:
            Generated response text
            
        Raises:
            ConnectionError: If unable to connect to Ollama
            TimeoutError: If request times out
            RuntimeError: If API returns an error
        """
        url = f"{self.base_url}/api/generate"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "options": {
                "num_ctx": num_ctx,
                "num_predict": num_predict,
                "temperature": 0.2,
                "top_p": 0.9,
            }
        }
        
        try:
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            if "response" in result:
                return result["response"]
            elif "error" in result:
                raise RuntimeError(f"Ollama API error: {result['error']}")
            else:
                raise RuntimeError(f"Unexpected Ollama response format: {result}")
                
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(
                f"Failed to connect to Ollama at {self.base_url}. "
                "Ensure Ollama is running. Details: {str(e)}"
            ) from e
        except requests.exceptions.Timeout as e:
            raise TimeoutError(
                f"Request to Ollama timed out after {self.timeout}s. Details: {str(e)}"
            ) from e
        except requests.exceptions.RequestException as e:
            raise RuntimeError(
                f"Request to Ollama failed: {str(e)}"
            ) from e

    def generate(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        max_iterations: int = 2
    ) -> Dict[str, Any]:
        """
        Generate Lua code with retry logic.
        
        Args:
            prompt: Description of the Lua code to generate
            context: Optional context dictionary with additional information
            max_iterations: Maximum number of generation attempts (default: 2)
            
        Returns:
            Dictionary with keys:
                - code: Generated Lua code (or empty string on failure)
                - iterations: Number of iterations performed
                - status: "ok" or "error"
                - error: Error message (only if status is "error")
        """
        system_prompt = self._build_system_prompt()
        
        # Build the full prompt with context if provided
        full_prompt = prompt
        if context:
            context_str = json.dumps(context, indent=2)
            full_prompt = f"Context:\n{context_str}\n\nTask:\n{prompt}"
        
        last_error = None
        
        for iteration in range(1, max_iterations + 1):
            try:
                # Call Ollama to generate code
                response_text = self._call_ollama(
                    prompt=full_prompt,
                    system_prompt=system_prompt,
                    num_ctx=4096,
                    num_predict=256
                )
                
                # Extract code from response
                code = self._extract_code_from_response(response_text)
                
                if code:
                    return {
                        "code": code,
                        "iterations": iteration,
                        "status": "ok"
                    }
                else:
                    last_error = f"Iteration {iteration}: Failed to extract code from response"
                    # Continue to next iteration
                    
            except (ConnectionError, TimeoutError, RuntimeError) as e:
                last_error = f"Iteration {iteration}: {str(e)}"
                # Continue to next iteration if we have retries left
                if iteration < max_iterations:
                    time.sleep(0.5)  # Brief delay before retry
                    continue
                else:
                    break
                    
        # All iterations failed
        return {
            "code": "",
            "iterations": max_iterations,
            "status": "error",
            "error": last_error
        }


def generate_lua(
    prompt: str,
    context: Optional[Dict[str, Any]] = None,
    max_iterations: int = 2
) -> Dict[str, Any]:
    """
    Convenience function to generate Lua code using default settings.
    
    Args:
        prompt: Description of the Lua code to generate
        context: Optional context dictionary with additional information
        max_iterations: Maximum number of generation attempts (default: 2)
        
    Returns:
        Dictionary with keys:
            - code: Generated Lua code (or empty string on failure)
            - iterations: Number of iterations performed
            - status: "ok" or "error"
            - error: Error message (only if status is "error")
    """
    agent = LuaAgent()
    return agent.generate(prompt=prompt, context=context, max_iterations=max_iterations)


if __name__ == "__main__":
    # Example usage
    result = generate_lua(
        prompt="Create a function that calculates the sum of two numbers",
        context={"function_name": "addNumbers"}
    )
    print(json.dumps(result, indent=2))
