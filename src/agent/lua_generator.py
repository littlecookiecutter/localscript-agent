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


def extract_lua_code(text: str) -> Optional[str]:
    """
    Extract Lua code from LLM response text.
    
    Searches for code blocks in the following formats:
    1. {"result":"lua{...}lua"} - preferred format
    2. ```lua ... ``` - markdown code blocks
    
    Args:
        text: Response text from the model (may contain explanations + code)
        
    Returns:
        Clean Lua code string or None if no code found
        
    Rules:
    1. Search for blocks in format {"result":"lua{...}lua"} or code between ```lua and ```
    2. If multiple blocks found, return the first one
    3. Remove markdown formatting if present
    4. Return None if code is not found
    """
    if not text:
        return None
    
    # Pattern 1: Match {"result":"lua{...}lua"} format
    # This is the preferred format from our system prompt
    json_pattern = r'\{\s*"result"\s*:\s*"lua\{(.+?)\}lua"'
    
    match = re.search(json_pattern, text, re.DOTALL)
    if match:
        code = match.group(1).strip()
        # Unescape JSON-escaped characters
        code = code.replace('\\"', '"').replace('\\n', '\n')
        code = code.replace('\\\\', '\\')
        # Remove any remaining markdown code fences
        code = re.sub(r'```lua\s*', '', code)
        code = re.sub(r'```\s*', '', code)
        return code.strip() if code else None
    
    # Pattern 2: Match ```lua ... ``` markdown blocks
    markdown_pattern = r'```lua\s*(.+?)\s*```'
    
    match = re.search(markdown_pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        code = match.group(1).strip()
        return code if code else None
    
    # Pattern 3: Match generic ``` ... ``` blocks (without lua specifier)
    generic_pattern = r'```\s*(.+?)\s*```'
    
    match = re.search(generic_pattern, text, re.DOTALL)
    if match:
        code = match.group(1).strip()
        # Check if it looks like Lua code
        if code:
            return code
    
    return None


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


# =============================================================================
# Tests for extract_lua_code function
# =============================================================================

def _run_tests():
    """Run unit tests for extract_lua_code function."""
    print("Running tests for extract_lua_code...\n")
    
    test_cases = [
        # Test 1: JSON format with lua{...}lua
        {
            "name": "JSON format with lua{...}lua",
            "input": 'Here is the code: {"result":"lua{local x = 5\nreturn x}lua"}',
            "expected": "local x = 5\nreturn x"
        },
        # Test 2: Markdown ```lua ... ``` block
        {
            "name": "Markdown lua code block",
            "input": "Some text before\n```lua\nlocal function add(a, b)\n    return a + b\nend\n```\nSome text after",
            "expected": "local function add(a, b)\n    return a + b\nend"
        },
        # Test 3: Generic ``` ... ``` block
        {
            "name": "Generic code block",
            "input": "```\nprint('Hello, World!')\n```",
            "expected": "print('Hello, World!')"
        },
        # Test 4: Multiple blocks - should return first
        {
            "name": "Multiple blocks (first one)",
            "input": '{"result":"lua{first_code()}lua"} and {"result":"lua{second_code()}lua"}',
            "expected": "first_code()"
        },
        # Test 5: With escaped characters
        {
            "name": "JSON with escaped characters",
            "input": '{"result":"lua{local s = \\"hello\\"\\nprint(s)}lua"}',
            "expected": 'local s = "hello"\nprint(s)'
        },
        # Test 6: Empty input
        {
            "name": "Empty input",
            "input": "",
            "expected": None
        },
        # Test 7: No code found
        {
            "name": "No code found",
            "input": "This is just plain text without any code",
            "expected": None
        },
        # Test 8: None input
        {
            "name": "None input",
            "input": None,
            "expected": None
        },
        # Test 9: Mixed content with explanations
        {
            "name": "Mixed content with explanations",
            "input": """Sure! Here's the Lua code you requested:

{"result":"lua{wf.vars.sum = wf.vars.a + wf.vars.b
return wf.vars.sum}lua"}

Let me know if you need anything else!""",
            "expected": "wf.vars.sum = wf.vars.a + wf.vars.b\nreturn wf.vars.sum"
        },
        # Test 10: Markdown with extra whitespace
        {
            "name": "Markdown with extra whitespace",
            "input": "```lua   \n  local x = 10  \n```",
            "expected": "local x = 10"
        },
        # Test 11: Case insensitive lua marker
        {
            "name": "Case insensitive LUA marker",
            "input": "```LUA\nfunction test() end\n```",
            "expected": "function test() end"
        },
        # Test 12: JSON format with spaces
        {
            "name": "JSON format with spaces",
            "input": '{ "result" : "lua{return true}lua" }',
            "expected": "return true"
        },
    ]
    
    passed = 0
    failed = 0
    
    for i, test in enumerate(test_cases, 1):
        result = extract_lua_code(test["input"])
        expected = test["expected"]
        
        if result == expected:
            print(f"✓ Test {i}: {test['name']} - PASSED")
            passed += 1
        else:
            print(f"✗ Test {i}: {test['name']} - FAILED")
            print(f"  Input: {repr(test['input'][:50])}...")
            print(f"  Expected: {repr(expected)}")
            print(f"  Got: {repr(result)}")
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"Tests completed: {passed} passed, {failed} failed out of {len(test_cases)}")
    print(f"{'='*60}\n")
    
    return failed == 0


if __name__ == "__main__":
    import sys
    
    # Run tests first
    tests_passed = _run_tests()
    
    # Then run example usage
    print("\nExample usage:")
    print("-" * 40)
    result = generate_lua(
        prompt="Create a function that calculates the sum of two numbers",
        context={"function_name": "addNumbers"}
    )
    print(json.dumps(result, indent=2))
    
    # Exit with appropriate code
    sys.exit(0 if tests_passed else 1)
