import base64                    # For encoding images to text
import httpx                     # For making HTTP calls to Ollama
import json                      # For parsing JSON responses
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware  # Allows browser to talk to us
from pydantic import BaseModel 

app=FastAPI()
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
OLLAMA_BASE_URL = "http://localhost:11434"
VISION_MODEL = "llava"           # For: photo → ingredient list
DECISION_MODEL = "llama3.2"  

class DecisionResponse(BaseModel):
    verdict: str                 # "COOK" or "ORDER"
    confidence: str              # "high" / "medium" / "low"
    ingredients_found: list[str] # What the vision model spotted
    recipe_or_order: str         # The actual suggestion
    reasoning: str               # Why this decision was made
    effort_level: str   

async def extract_ingredients(image_bytes: bytes) -> list[str]:
    print("🔍 Stage 1: Sending image to vision model...")
 
    # Convert image bytes to base64 string so it fits in JSON
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
 
    # This is our "prompt" — the instruction to the vision model.
    # Notice: we ask for JSON output. This is called "structured output".
    prompt = """Look at this fridge/pantry image carefully.
List ONLY the food ingredients and items you can clearly see.
Respond with ONLY a JSON array of strings. No other text.
Example: ["eggs", "milk", "cheddar cheese", "leftover rice", "soy sauce"]
Be specific but concise. Include quantities if visible (e.g., "3 eggs", "half bottle of ketchup")."""
 
    # Build the request payload for Ollama's API
    # This is the standard format Ollama expects
    payload = {
        "model": VISION_MODEL,
        "prompt": prompt,
        "images": [image_base64],    # Images go here as base64 strings
        "stream": False,             # False = wait for full response
        "options": {
            "temperature": 0.1,      # Low temp = more predictable/consistent output
                                     # High temp = more creative/random
        }
    }
 
    # Make the HTTP request to Ollama
    # httpx.AsyncClient is like requests but async (non-blocking)
    # "async" means: don't freeze while waiting for the response
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload
        )
 
        if response.status_code != 200:
            raise HTTPException(500, f"Vision model error: {response.text}")
 
        # Ollama returns: {"response": "...", "done": true, ...}
        result = response.json()
        raw_text = result.get("response", "")
 
    print(f"📋 Vision model raw output: {raw_text[:200]}...")
 
    # Parse the JSON array from the response
    # The model might wrap it in markdown code blocks, so we clean it
    try:
        # Strip markdown code fences if present: ```json ... ```
        clean_text = raw_text.strip()
        if clean_text.startswith("```"):
            clean_text = clean_text.split("```")[1]
            if clean_text.startswith("json"):
                clean_text = clean_text[4:]
 
        parsed = json.loads(clean_text)

        if isinstance(parsed, list):
            ingredients = [
                item.strip()
                for item in parsed
                if isinstance(item, str) and item.strip()
            ]
        elif isinstance(parsed, dict):
            # Handle categorized output such as {"fruit": ["apples"], "dairy": ["milk"]}
            ingredients = []
            for items in parsed.values():
                if isinstance(items, str):
                    items = [items]
                if isinstance(items, list):
                    ingredients.extend(
                        item.strip()
                        for item in items
                        if isinstance(item, str) and item.strip()
                    )
        else:
            raise HTTPException(502, "Vision model returned an unexpected response format")

        print(f"✅ Stage 1 complete. Found {len(ingredients)} ingredients.")
        return ingredients
        
    except json.JSONDecodeError:
        # Fallback: split by commas/newlines if JSON parsing fails
        print("⚠️  JSON parse failed, using fallback extraction...")
        lines = [line.strip().strip('"-,[]') for line in raw_text.split('\n')]
        return [l for l in lines if l and len(l) > 2]
 
        
async def cook_or_order(ingredients : list[str])-> dict:
    print("🧠 Stage 2: Sending ingredients to decision model...")
    ingredients_str = "\n".join(f"- {item}" for item in ingredients)
    prompt = f"""You are a lazy but resourceful home cook. Your job is to decide:
Should someone COOK with what's available, or ORDER delivery instead?
 
AVAILABLE INGREDIENTS:
{ingredients_str}
 
DECISION RULES:
- COOK if: there are 3+ real ingredients that form a coherent meal (protein + carb/veg, or a complete dish)
- ORDER if: ingredients are condiments only, too few items, or would make a sad/incomplete meal
- Be honest — if it's really not worth cooking, say ORDER
 
Respond ONLY with this exact JSON (no other text):
{{
  "verdict": "COOK" or "ORDER",
  "confidence": "high" or "medium" or "low",
  "recipe_or_order": "If COOK: exact recipe name + 3-step instructions. If ORDER: suggest a specific dish category to order (e.g., 'Thai takeout - pad see ew')",
  "reasoning": "One sentence: why this decision",
  "effort_level": "If COOK: estimated time like '15 min'. If ORDER: 'delivery time ~30 min'",
  "laziness_score": "1-10 where 10 = maximum laziness (ordering)"
}}"""
    payload = {
        "model": DECISION_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,  # Slightly creative but mostly consistent
        }
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload
        )
        if response.status_code != 200:
            raise HTTPException(500, f"Decision model error: {response.text}")
 
        result = response.json()
        raw_text = result.get("response", "")
 
    print(f"🤔 Decision model raw output: {raw_text[:300]}...")
 
    # Parse the JSON response
    try:
        clean_text = raw_text.strip()
        # Handle markdown code blocks
        if "```" in clean_text:
            parts = clean_text.split("```")
            for part in parts:
                if "{" in part:
                    clean_text = part
                    if clean_text.startswith("json"):
                        clean_text = clean_text[4:]
                    break
 
        decision = json.loads(clean_text.strip())
        print(f"✅ Stage 2 complete. Verdict: {decision.get('verdict')}")
        return decision
 
    except json.JSONDecodeError as e:
        print(f"⚠️  Decision JSON parse failed: {e}")
        # Fallback response
        return {
            "verdict": "ORDER",
            "confidence": "low",
            "recipe_or_order": "Couldn't analyze properly — just order something",
            "reasoning": "Analysis failed",
            "effort_level": "~30 min delivery",
            "laziness_score": "8"
        }
@app.post("/analyze", response_model=DecisionResponse)
async def analyze_fridge(photo: UploadFile = File(...)):
    """
    THE FULL PIPELINE ENDPOINT
 
    CONCEPT: HTTP Endpoints
    This is a "route" — when the browser sends a POST request to /analyze
    with an image file, this function runs.
 
    CONCEPT: async/await
    "async def" means this function doesn't block.
    "await" means: pause here and let other requests run while waiting.
    This makes our server handle multiple users simultaneously.
 
    CONCEPT: File Upload
    UploadFile is FastAPI's way of receiving binary files.
    We read the bytes, then pass them through our pipeline.
    """
    print(f"\n🚀 New request: analyzing {photo.filename}")
 
    # Validate file type
    if not photo.content_type.startswith("image/"):
        raise HTTPException(400, "Please upload an image file")
 
    # Read the image bytes from the upload
    image_bytes = await photo.read()
    print(f"📸 Received image: {len(image_bytes)} bytes")
 
    # ── PIPELINE EXECUTION ──────────────────────────────────────────
    # Stage 1: Extract ingredients from the image
    ingredients = await extract_ingredients(image_bytes)
 
    if not ingredients:
        raise HTTPException(422, "Couldn't identify any ingredients. Try a clearer photo.")
 
    # Stage 2: Decide cook or order
    decision = await cook_or_order(ingredients)
    # ────────────────────────────────────────────────────────────────
 
    # Build and return the final response
    return DecisionResponse(
        verdict=decision.get("verdict", "ORDER"),
        confidence=decision.get("confidence", "medium"),
        ingredients_found=ingredients,
        recipe_or_order=decision.get("recipe_or_order", "Order takeout"),
        reasoning=decision.get("reasoning", ""),
        effort_level=decision.get("effort_level", "Unknown"),
    )
 
 
# ─── HEALTH CHECK ─────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    """
    A simple endpoint to verify the server is running.
    Also checks if Ollama is reachable.
    This is good practice for any API.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            models = response.json().get("models", [])
            model_names = [m["name"] for m in models]
 
        return {
            "status": "ok",
            "ollama": "connected",
            "available_models": model_names,
            "vision_model_ready": any(VISION_MODEL in m for m in model_names),
            "decision_model_ready": any(DECISION_MODEL in m for m in model_names),
        }
    except Exception as e:
        return {
            "status": "ok",
            "ollama": f"not reachable: {str(e)}",
            "tip": "Make sure Ollama is running: `ollama serve`"
        }
 
 
# ─── ENTRY POINT ──────────────────────────────────────────────────────────────
# This runs only when you execute: python main.py
# (Not when imported as a module)
if __name__ == "__main__":
    import uvicorn
    # uvicorn is the "server" that actually listens for requests
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)