from pydantic import BaseModel, Field
from enum import Enum


class VoiceStyle(str, Enum):
    # Voice styles for gTTS (these map to gTTS parameters)
    normal = "normal"
    slow = "slow"
    fast = "fast"
    # Note: gTTS doesn't have specific voice names like OpenAI


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)  # gTTS has limits
    speed: VoiceStyle = VoiceStyle.normal  # gTTS speed option
    language: str = "en"  # Default language


class PPTXProcessRequest(BaseModel):
    # Parameters for the full PPTX processing workflow
    voice_speed: VoiceStyle = VoiceStyle.normal
    language: str = "en"
