# 🔄 Model Loading & Architecture Diagrams

## 1. Bot Startup Flow

```
START
  ↓
main.py execution
  ↓
load .env variables
  ├─ DISCORD_TOKEN
  ├─ LLM_MODEL_NAME → "Qwen/Qwen3-1.7B-Instruct"
  ├─ LLM_MODEL_PATH → "./models/Qwen3-1.7B-Instruct"
  ├─ LLM_DEVICE → "cpu"
  └─ LLM_DTYPE → "float32"
  ↓
bot.run(DISCORD_TOKEN)
  ↓
on_ready() event triggered
  ├─ print("Loading LLM model...")
  ├─ load_llm() called
  │   ├─ Check if LLM_MODEL_PATH exists locally?
  │   │   ├─ YES → Load from ./models/ (fast, ~2-5s)
  │   │   └─ NO → Download from HuggingFace (slow, ~10-20 min)
  │   ├─ Load tokenizer
  │   ├─ Load model onto device (cpu/cuda)
  │   └─ Return True/False
  ├─ Load Discord cogs
  └─ Sync slash commands
  ↓
✅ Bot READY - Waiting for commands
```

## 2. Game Turn Flow

```
Player types /newgame [scenario]
  ↓
game_commands.py → create_game()
  ├─ Generate random map (map_generator.py)
  ├─ Initialize player stats
  ├─ Create Discord channel for game
  └─ Display game dashboard (game_ui.py)
  ↓
Show embed with:
┌─────────────────────────┐
│  🏨 HORROR HOTEL        │
│  Floor: 3, Room: 5      │
│                         │
│  🕷️ HP: [███░░░░] 70    │
│  😨 Sanity: [████░] 80  │
│                         │
│  [⚔️ Attack] [🏃 Flee]  │
│  [🔍 Search]            │
└─────────────────────────┘
  ↓
Players select action
  ├─ Click button
  ├─ Button callback → game_ui.py
  ├─ Send ephemeral message "Action received"
  ├─ Register action in game_engine.py
  └─ Check if all players acted or timeout?
  ↓
If all players acted OR timeout reached:
  ├─ Gather all player actions
  ├─ Resolve actions (calculate damage, etc)
  ├─ Call describe_scene() → llm_service.py
  │   ├─ LLM generates scene description
  │   ├─ Runs in executor (non-blocking)
  │   └─ Returns description text
  ├─ Update player stats
  ├─ Generate new embed
  └─ Loop back to "Show embed"
  ↓
Player quits or game ends
  └─ END GAME
```

## 3. LLM Service Architecture

```
describe_scene(context_keywords)
  ↓
  [Check Model Loaded]
  ├─ get_llm() → Returns global llm_model
  ├─ get_tokenizer() → Returns global llm_tokenizer
  └─ If None → Return fallback text "The air is thick..."
  ↓
  [Prepare Input]
  ├─ prompt = f"Describe: {context_keywords}"
  ├─ messages = [{"role": "user", "content": prompt}]
  ├─ text = tokenizer.apply_chat_template(messages)
  └─ model_inputs = tokenizer(text, return_tensors="pt")
  ↓
  [Run in Executor] (non-blocking async)
  └─ generate():
      ├─ model.generate(max_new_tokens=150, ...)
      ├─ torch.no_grad() to save memory
      ├─ Return decoded text
      └─ ~20-45 seconds on CPU
  ↓
  [Post-Process]
  ├─ Strip special tokens
  ├─ Clean whitespace
  └─ Return description
  ↓
  description → game_engine → embed → Discord
```

## 4. Model Loading Path Comparison

### Scenario 1: First Time Run (No Local Model)

```
start
  ↓
check ./models/Qwen3-1.7B-Instruct/
  ↓
Not found!
  ↓
Download from HuggingFace:
├─ Qwen/Qwen3-1.7B-Instruct (tokenizer)
└─ Qwen/Qwen3-1.7B-Instruct (model)
  ↓
Save to ./models/Qwen3-1.7B-Instruct/
  ├─ config.json
  ├─ generation_config.json
  ├─ model.safetensors (or .bin)
  ├─ tokenizer.json
  ├─ tokenizer.model
  ├─ tokenizer_config.json
  └─ other files
  ↓
Model loaded, ready to use
(Next time: Use cached version)
```

### Scenario 2: Cached Model Run

```
start
  ↓
check ./models/Qwen3-1.7B-Instruct/
  ↓
Found! Load immediately
  ├─ Load tokenizer from disk (~500ms)
  ├─ Load model weights (~3-5s on CPU)
  └─ Ready to generate
  ↓
Model loaded, ready to use
(Instant, no download needed)
```

## 5. File Organization

```
horror_bot_project/
│
├── .env  ← Model configuration (DYNAMIC!)
│   └─ LLM_MODEL_NAME="Qwen/Qwen3-1.7B-Instruct"
│   └─ LLM_MODEL_PATH="./models/Qwen3-1.7B-Instruct"
│   └─ LLM_DEVICE="cpu"
│   └─ LLM_DTYPE="float32"
│
├── horror_bot/
│   ├── main.py
│   │   └─ Call load_llm() on startup
│   │
│   ├── services/llm_service.py  ← Core LLM wrapper
│   │   ├─ load_llm()
│   │   ├─ get_llm()
│   │   ├─ get_tokenizer()
│   │   └─ describe_scene()
│   │
│   ├── models/  ← Model storage (auto-created)
│   │   └── Qwen3-1.7B-Instruct/
│   │       ├── config.json
│   │       ├── model.safetensors (~3.2GB)
│   │       ├── tokenizer.json
│   │       └── ... (other files)
│   │
│   ├── cogs/
│   ├── database/
│   └── data/
│
├── download_model.py  ← Initial model download script
│
└── setup_and_run.sh/bat  ← Auto-setup script
```

## 6. Memory & Performance Profile

### CPU Execution (Qwen3-1.7B float32)

```
Model Size: 3.2GB
Tokenizer: ~50MB
Context: ~512 tokens

RAM Usage:
├─ Model weights: 3.2GB
├─ Forward pass buffer: ~500MB
├─ Attention cache: ~200MB
└─ Total: ~3.9GB

Inference Time:
├─ Tokenization: 10-20ms
├─ Generation: 15-45s (150 tokens)
├─ Decoding: 50-100ms
└─ Total: 15-46s per description

Bottleneck: Model.generate() on CPU
```

### GPU Execution (Qwen3-1.7B float16)

```
Model Size: 1.6GB (half precision)
VRAM Usage: 3.5GB

Inference Time:
├─ Tokenization: 5-10ms
├─ Generation: 1-3s (150 tokens)
├─ Decoding: 20-50ms
└─ Total: 2-4s per description (10x faster!)

Bottleneck: None (GPU fast enough)
```

## 7. Error Handling Flow

```
describe_scene() called
  ↓
try:
  ├─ Get model and tokenizer
  │   └─ If None → return fallback text
  ├─ Prepare inputs
  ├─ Run generate()
  └─ Decode output
catch Exception:
  ├─ print error log
  ├─ return "A mysterious presence fills the room..."
  └─ Continue game (graceful degradation)
  ↓
Game continues with AI-less descriptions
(Low quality but playable)
```

## 8. Model Switching Workflow

```
Want to switch model?
  ↓
1. Edit .env:
   LLM_MODEL_NAME="mistralai/Mistral-7B-Instruct-v0.1"
   LLM_MODEL_PATH="./models/Mistral-7B-Instruct"
  ↓
2. Run download_model.py
   (downloads new model to new path)
  ↓
3. Restart bot
   (load_llm() detects new path, loads new model)
  ↓
✅ Bot now uses new model
(No code changes needed!)
```

## 9. Async Architecture

```
Discord Event (player clicks button)
  ↓
Button callback (async)
  ├─ Register action
  ├─ Send ephemeral response immediately
  └─ Check if all acted
  ↓
If ready, start turn resolution
  ├─ Resolve game logic (fast)
  └─ Call describe_scene()
  ↓
describe_scene() (async)
  ├─ Prepare input
  └─ await loop.run_in_executor(None, generate)
      ├─ Blocks in thread pool (doesn't block bot)
      ├─ Bot can handle other events
      └─ Returns description after 20-45s
  ↓
Update embed and send
  ↓
Bot continues handling other users
```

## 10. Configuration Precedence

```
System Default Values (hardcoded in code)
  ↑
Environment Variables from .env (override defaults)
  ↑
CLI Arguments (override .env if implemented)
  ↑
Final Configuration Used
```

Example:
```python
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "Qwen/Qwen3-1.7B-Instruct")
                                 ↑                    ↑
                           reads from .env      fallback default
```

---

## Summary

✅ **Dynamic Loading** - Model path & name from .env  
✅ **Auto-Download** - First-time setup automatic  
✅ **Local Cache** - Subsequent runs use cached model  
✅ **Async Execution** - Non-blocking bot operation  
✅ **Graceful Fallback** - Works even if LLM disabled  
✅ **Easy Switching** - Change model by editing .env  
