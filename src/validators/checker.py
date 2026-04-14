"""Lua code validator for LowCode platform."""

import logging
import re
import subprocess
from typing import Dict, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def validate_lua(code: str) -> Dict:
    """
    Validate Lua code for syntax and LowCode rules.
    
    Args:
        code: Lua source code as string
        
    Returns:
        dict with keys: valid (bool), errors (list[str]), warnings (list[str])
    """
    result = {
        "valid": True,
        "errors": [],
        "warnings": []
    }
    
    # 1. Syntax check using luac
    try:
        proc = subprocess.run(
            ["luac", "-p", "-"],
            input=code,
            capture_output=True,
            text=True
        )
        if proc.returncode != 0:
            result["valid"] = False
            error_msg = proc.stderr.strip()
            if error_msg:
                result["errors"].append(error_msg)
    except FileNotFoundError:
        logger.warning("luac not found, syntax skipped")
        result["warnings"].append("luac not found, syntax skipped")
    
    # 2. LowCode rules (string-based checks)
    
    # Error: empty code or only comments
    stripped_code = code.strip()
    if not stripped_code:
        result["valid"] = False
        result["errors"].append("Code is empty")
    else:
        # Remove single-line comments
        no_comments = re.sub(r'--[^\n]*', '', stripped_code)
        # Remove multi-line comments
        no_comments = re.sub(r'--\[\[.*?\]\]', '', no_comments, flags=re.DOTALL)
        no_comments = no_comments.strip()
        
        if not no_comments:
            result["valid"] = False
            result["errors"].append("Code contains only comments")
    
    # Warning: no wf.vars or wf.initVariables references
    if "wf.vars" not in code and "wf.initVariables" not in code:
        result["warnings"].append("No wf.vars or wf.initVariables references found")
    
    # Warning: found "$.", "JsonPath", "wf.data."
    suspicious_patterns = ["$.", "JsonPath", "wf.data."]
    for pattern in suspicious_patterns:
        if pattern in code:
            result["warnings"].append(f"Found suspicious pattern: {pattern}")
    
    # Warning: no 'return' keyword at the end
    # Check if there's a 'return' statement near the end of the code
    lines = [line.strip() for line in code.split('\n') if line.strip()]
    has_return = False
    for line in reversed(lines):
        # Skip comments
        if line.startswith('--'):
            continue
        if line.startswith('return'):
            has_return = True
            break
        # If we hit any non-return, non-comment code, stop checking
        if line and not line.startswith('--'):
            break
    
    if not has_return:
        result["warnings"].append("No 'return' keyword found at the end of code")
    
    return result


if __name__ == "__main__":
    # Example usage
    test_code_valid = """
    local x = wf.vars.get("input")
    local result = x * 2
    return result
    """
    
    test_code_invalid = """
    -- This is just a comment
    -- Another comment
    """
    
    test_code_warnings = """
    local data = $.store
    local json = JsonPath.parse(data)
    local val = wf.data.value
    local x = 5
    """
    
    print("=== Test 1: Valid code ===")
    result1 = validate_lua(test_code_valid)
    print(f"Valid: {result1['valid']}")
    print(f"Errors: {result1['errors']}")
    print(f"Warnings: {result1['warnings']}")
    
    print("\n=== Test 2: Only comments ===")
    result2 = validate_lua(test_code_invalid)
    print(f"Valid: {result2['valid']}")
    print(f"Errors: {result2['errors']}")
    print(f"Warnings: {result2['warnings']}")
    
    print("\n=== Test 3: Code with warnings ===")
    result3 = validate_lua(test_code_warnings)
    print(f"Valid: {result3['valid']}")
    print(f"Errors: {result3['errors']}")
    print(f"Warnings: {result3['warnings']}")