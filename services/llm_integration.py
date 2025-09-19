import os
import httpx
from typing import List


class LLMIntegration:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.base_url = "https://openrouter.ai/api/v1"

    async def generate_transcript(self, slide_texts: List[str]) -> List[str]:
        """Generate enhanced transcripts for each slide using OpenRouter"""
        transcripts = []

        for i, text in enumerate(slide_texts):
            if not text.strip():
                transcripts.append("")
                continue

            try:
                transcript = await self._call_openrouter(text, i+1)
                transcripts.append(transcript)
            except Exception as e:
                print(f"Error generating transcript for slide {i+1}: {str(e)}")
                transcripts.append(text)  # Fallback to original text

        return transcripts

    async def _call_openrouter(self, text: str, slide_num: int) -> str:
        """Make API call to OpenRouter"""
        prompt = f"""
        You are a professional voiceover artist. Create a natural-sounding transcript 
        for a slide presentation based on the following content from slide {slide_num}:
        
        {text}
        
        Make it sound conversational and engaging, suitable for a voiceover.
        Keep it concise but comprehensive.
        """

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        data = {
            # You can change this to any model supported by OpenRouter
            "model": "openai/gpt-3.5-turbo",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=30.0
            )

            if response.status_code != 200:
                raise Exception(f"OpenRouter API error: {response.text}")

            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
