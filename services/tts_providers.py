import os
from dotenv import load_dotenv
from gtts import gTTS
import io
import asyncio

load_dotenv()  # Load API keys from .env file


class TTSProvider:
    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY")

    async def generate_speech_gtts(self, text: str, language: str = 'en', slow: bool = False) -> bytes:
        """Use gTTS (Google Text-to-Speech) as primary TTS service."""
        try:
            # Run gTTS in a thread pool since it's synchronous
            loop = asyncio.get_event_loop()
            audio_bytes = await loop.run_in_executor(
                None, self._gtts_sync, text, language, slow
            )
            return audio_bytes
        except Exception as e:
            print(f"gTTS failed: {str(e)}")
            # Fall back to OpenAI if available
            if self.openai_api_key:
                return await self.generate_speech_openai(text, "alloy", "tts-1")
            raise Exception(f"All TTS providers failed: {str(e)}")

    def _gtts_sync(self, text: str, language: str, slow: bool) -> bytes:
        """Synchronous gTTS implementation for thread pool execution."""
        tts = gTTS(text=text, lang=language, slow=slow)
        audio_buffer = io.BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)
        return audio_buffer.getvalue()

    async def generate_speech_openai(self, text: str, voice: str, model: str) -> bytes:
        """Optional: OpenAI TTS as fallback if gTTS fails and API key is available."""
        if not self.openai_api_key:
            raise ValueError("OpenAI API key not configured")

        import httpx
        url = "https://api.openai.com/v1/audio/speech"
        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": model,
            "voice": voice,
            "input": text,
            "response_format": "mp3"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=data, headers=headers)
                response.raise_for_status()
                return response.content
        except Exception as e:
            print(f"OpenAI TTS failed: {str(e)}")
            raise

    async def generate_speech(self, text: str, **kwargs) -> bytes:
        """
        Main method for TTS generation.
        Uses gTTS as primary, falls back to OpenAI if available.
        """
        # gTTS has a character limit, so we need to handle long text
        if len(text) > 4000:
            print("Text too long for gTTS, using OpenAI if available")
            if self.openai_api_key:
                try:
                    return await self.generate_speech_openai(
                        text,
                        kwargs.get('voice', 'alloy'),
                        kwargs.get('model', 'tts-1')
                    )
                except Exception as openai_error:
                    print(f"OpenAI also failed: {str(openai_error)}")
                    raise Exception("Text too long and OpenAI failed")
            else:
                raise Exception(
                    "Text too long for gTTS and no OpenAI fallback configured")

        try:
            # Try gTTS first
            return await self.generate_speech_gtts(text, **kwargs)
        except Exception as e:
            print(f"Primary gTTS failed, attempting fallback: {str(e)}")
            # If gTTS fails and OpenAI is configured, try it
            if self.openai_api_key:
                try:
                    return await self.generate_speech_openai(
                        text,
                        kwargs.get('voice', 'alloy'),
                        kwargs.get('model', 'tts-1')
                    )
                except Exception as openai_error:
                    print(f"OpenAI fallback also failed: {str(openai_error)}")
                    raise Exception("All TTS providers failed")
            raise
