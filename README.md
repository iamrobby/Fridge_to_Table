# 🧊 Fridge Decider — Local AI Pipeline

## Architecture

```
Photo
  │
  ▼
[FastAPI Server]  ← Your Python backend (the "orchestrator")
  │
  ├─ Stage 1 ──► [Ollama + LLaVA]     → "I see eggs, cheese, leftover rice..."
  │                 (Vision Model)
  │
  └─ Stage 2 ──► [Ollama + Llama3.2]  → "COOK: Make fried rice. 10 min."
                    (Language Model)
                         │
                         ▼
                    [Browser UI]  ← Your HTML frontend
```

---

## Intallations

| Tool | Purpose | Why Local? |
|------|---------|-----------|
| **Python + FastAPI** | The server that runs your pipeline | It's your code |
| **Ollama** | Runs AI models locally on your GPU/CPU | Privacy, free, no API key |
| **LLaVA** | Vision model — understands images | Replaces GPT-4 Vision |
| **Llama3.2** | Language model — makes decisions | Replaces GPT-4 |

---

## Step 1: Install Ollama

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Windows → download from https://ollama.ai
```

Start Ollama:
```bash
ollama serve
# This runs in the background. Keep this terminal open.
```

---

## Step 2: Pull the AI Models

```bash
# Vision model — can see images (about 4GB)
ollama pull llava

# Language model — fast and smart (about 2GB)
ollama pull llama3.2

# Verify they're installed
ollama list
```

**Why these models?**
- `llava` = LLaVA (Large Language and Vision Assistant) — processes text + images
- `llama3.2` = Meta's Llama 3.2 — fast inference, good reasoning

**Lighter alternatives if storage is tight:**
```bash
ollama pull llava:7b          # Smaller LLaVA
ollama pull llama3.2:1b       # Tiny but still usable
```

---

## Step 3: Set Up the Python Backend

```bash
cd backend

# Create a virtual environment (isolated Python environment — good practice!)
python -m venv venv

# Activate it
source venv/bin/activate    # macOS/Linux
venv\Scripts\activate       # Windows

# Install dependencies
pip install -r requirements.txt
```

---

## Step 4: Run the Backend

```bash
# Make sure you're in the backend/ folder and venv is activated
uvicorn main:app --reload --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

Test it: http://localhost:8000/health

---

## Step 5: Open the Frontend

Just open `frontend/index.html` in your browser.
No build step needed — it's pure HTML/JS.

```bash
# macOS
open frontend/index.html

# Linux
xdg-open frontend/index.html

# Or just drag the file into Chrome/Firefox
```

---

## Step 6: Test It!

1. Take a photo of your fridge or find one online
2. Drop it in the upload zone
3. Click "Analyze My Fridge"
4. Watch the pipeline stages light up!

---


## Troubleshooting

**"Connection refused" on /analyze**
→ Make sure FastAPI is running: `uvicorn main:app --reload --port 8000`

**"Vision model error"**
→ Make sure Ollama is running: `ollama serve`
→ Make sure LLaVA is installed: `ollama pull llava`

**Slow responses (2-3 min)**
→ Normal for CPU inference. With an NVIDIA GPU + CUDA, it'll be 10-20x faster.
→ Try `llava:7b` instead of `llava` for faster but less accurate results.

**JSON parse errors in logs**
→ The model returned malformed JSON. The code has fallback handling.
→ Try a different model: `ollama pull mistral` and change DECISION_MODEL

---

## Project Structure

```
fridge-decider/
├── backend/
│   ├── main.py           ← The pipeline (Stage 1 + Stage 2 + FastAPI routes)
│   └── requirements.txt  ← Python dependencies
├── frontend/
│   └── index.html        ← The UI (pure HTML/CSS/JS)
└── README.md             ← This file
```
