"""FastAPI application for Lua code generation."""

import logging
import sys
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Setup path for imports
sys.path.append(os.path.dirname(os.path.abspath(os.path.join(__file__, '..'))))

from agent.generator import LuaAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Lua Code Generator API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize agent
agent = LuaAgent()


class GenerateRequest(BaseModel):
    """Request body for /generate endpoint."""
    prompt: str


class GenerateResponse(BaseModel):
    """Response body for /generate endpoint."""
    code: str


@app.post("/generate", response_model=GenerateResponse)
async def generate_code(request: GenerateRequest):
    """
    Generate Lua code based on a prompt.

    Returns:
        200: {"code": "<generated_lua_code>"}
        400: {"detail": "Prompt is required"}
        500: {"code": "-- Error during generation: <error_message>"}
    """
    logger.info(f"Received request with prompt: {request.prompt[:100]}...")

    # Validate prompt
    if not request.prompt or not request.prompt.strip():
        logger.warning("Empty prompt received")
        raise HTTPException(status_code=400, detail="Prompt is required")

    # Generate code
    result = agent.generate(request.prompt)

    if result["status"] == "ok":
        logger.info(f"Code generated successfully in {result['iterations']} iterations")
        return GenerateResponse(code=result["code"])
    else:
        error_msg = result.get("error", "Unknown error")
        logger.error(f"Generation failed: {error_msg}")
        error_code = f"-- Error during generation: {error_msg}"
        return GenerateResponse(code=error_code)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting server on 0.0.0.0:8080")
    uvicorn.run(app, host="0.0.0.0", port=8080)