from routers.tts import router as tts_router
from dotenv import load_dotenv
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI
import os
import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.append(str(Path(__file__).parent))


load_dotenv()

# Import after adding to path

# Add this before the app definition in main.py
os.makedirs(os.getenv("UPLOAD_FOLDER", "./uploads"), exist_ok=True)
os.makedirs(os.getenv("OUTPUT_FOLDER", "./output"), exist_ok=True)

# Increase maximum request size to 200MB (for large PPTX files)
middleware = [
    Middleware(TrustedHostMiddleware, allowed_hosts=["*"])
]

app = FastAPI(
    title="P&C Voice-Over Generator",
    version="1.0.0",
    middleware=middleware,
    max_request_size=200 * 1024 * 1024  # 200MB
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(tts_router, prefix="/api/tts", tags=["TTS"])

# Serve static files for UI
app.mount("/", StaticFiles(directory="static", html=True), name="static")


@app.get("/")
async def root():
    return {"message": "P&C Voice-Over Generator API"}

if __name__ == "__main__":
    import uvicorn
    # Increase timeout for long-running requests (like video generation)
    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8005)),
        timeout_keep_alive=300  # 5 minutes timeout
    )
