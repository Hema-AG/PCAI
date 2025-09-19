# services/video_generator.py
import os
import tempfile
import asyncio
import subprocess
import json
from typing import List
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
from services.tts_providers import TTSProvider


class VideoGenerator:
    def __init__(self):
        self.tts_provider = TTSProvider()
        self.temp_files = []  # Track temp files for cleanup

    async def create_video(self, slide_images: List[str], transcripts: List[str],
                           output_filename: str, voice_speed: str = "normal",
                           language: str = "en") -> str:
        """Create a video from slides and transcripts with efficient chunking"""
        print(f"Starting video generation for {len(slide_images)} slides")

        # Create output directory if it doesn't exist
        output_dir = os.getenv("OUTPUT_FOLDER", "./output")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, output_filename)

        # Process in optimized chunks
        optimal_chunk_size = self._calculate_optimal_chunk_size(
            len(slide_images))
        print(f"Processing in chunks of {optimal_chunk_size} slides")

        all_video_clips = []

        for chunk_idx, i in enumerate(range(0, len(slide_images), optimal_chunk_size)):
            chunk_images = slide_images[i:i + optimal_chunk_size]
            chunk_transcripts = transcripts[i:i + optimal_chunk_size]

            print(
                f"Processing chunk {chunk_idx + 1}: slides {i + 1} to {i + len(chunk_images)}")

            # Process this chunk
            chunk_video_path = await self._process_chunk(
                chunk_images, chunk_transcripts, chunk_idx,
                voice_speed, language
            )

            if chunk_video_path and os.path.exists(chunk_video_path):
                all_video_clips.append(chunk_video_path)

        # Combine all chunks into final video
        if all_video_clips:
            await self._combine_chunks(all_video_clips, output_path)
            print(f"Final video created at: {output_path}")

        # Cleanup temporary files
        self._cleanup_temp_files()

        return output_path

    def _calculate_optimal_chunk_size(self, total_slides: int) -> int:
        """Calculate the optimal chunk size based on total slides"""
        if total_slides <= 5:
            return total_slides  # Small presentation, no need to chunk
        elif total_slides <= 15:
            return 5  # Medium presentation, chunk into groups of 5
        else:
            return 8  # Large presentation, chunk into groups of 8

    async def _process_chunk(self, slide_images: List[str], transcripts: List[str],
                             chunk_idx: int, voice_speed: str, language: str) -> str:
        """Process a chunk of slides and return the video path"""
        try:
            # Create a temporary file for this chunk
            temp_dir = tempfile.gettempdir()
            chunk_video_path = os.path.join(temp_dir, f"chunk_{chunk_idx}.mp4")
            self.temp_files.append(chunk_video_path)

            # Generate audio files for all slides in this chunk first
            audio_files = []
            for i, transcript in enumerate(transcripts):
                audio_path = await self._generate_audio_for_slide(
                    transcript, f"chunk{chunk_idx}_slide{i}", voice_speed, language
                )
                audio_files.append(audio_path)

            # Create clips for each slide
            slide_clips = []
            for i, (image_path, audio_path) in enumerate(zip(slide_images, audio_files)):
                if not os.path.exists(image_path):
                    print(f"Warning: Image path does not exist: {image_path}")
                    continue

                # Get duration from audio file
                duration = await self._get_audio_duration(audio_path) if os.path.exists(audio_path) else 3.0

                # Create image clip
                image_clip = ImageClip(image_path).set_duration(duration)

                # Add audio if available
                if os.path.exists(audio_path):
                    audio_clip = AudioFileClip(audio_path)
                    image_clip = image_clip.set_audio(audio_clip)

                slide_clips.append(image_clip)

            # Concatenate all slides in this chunk
            if slide_clips:
                final_clip = concatenate_videoclips(
                    slide_clips, method="compose")

                # Write with optimized settings
                final_clip.write_videofile(
                    chunk_video_path,
                    fps=24,
                    codec="libx264",
                    audio_codec="aac",
                    threads=4,  # Use multiple threads
                    preset="fast",  # Faster encoding
                    ffmpeg_params=["-crf", "23", "-pix_fmt", "yuv420p"],
                    verbose=False,
                    logger=None
                )

                # Close clips to free memory
                final_clip.close()
                for clip in slide_clips:
                    clip.close()

            return chunk_video_path

        except Exception as e:
            print(f"Error processing chunk {chunk_idx}: {str(e)}")
            return None

    async def _combine_chunks(self, chunk_paths: List[str], output_path: str):
        """Combine all chunk videos into a final video using FFmpeg directly"""
        if not chunk_paths:
            return

        # If only one chunk, just rename it
        if len(chunk_paths) == 1:
            os.rename(chunk_paths[0], output_path)
            return

        # Create a file listing all chunks for FFmpeg concat
        concat_file = os.path.join(tempfile.gettempdir(), "concat_list.txt")
        self.temp_files.append(concat_file)

        with open(concat_file, "w") as f:
            for chunk_path in chunk_paths:
                f.write(f"file '{os.path.abspath(chunk_path)}'\n")

        # Use FFmpeg to concatenate (much faster than moviepy)
        ffmpeg_cmd = [
            "ffmpeg", "-f", "concat", "-safe", "0", "-i", concat_file,
            "-c", "copy",  # Stream copy (no re-encoding)
            "-y",  # Overwrite output file if exists
            output_path
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                print(f"FFmpeg concat error: {stderr.decode()}")
                # Fallback to moviepy if FFmpeg fails
                await self._combine_with_moviepy(chunk_paths, output_path)

        except Exception as e:
            print(f"FFmpeg concat failed: {str(e)}")
            # Fallback to moviepy
            await self._combine_with_moviepy(chunk_paths, output_path)

    async def _combine_with_moviepy(self, chunk_paths: List[str], output_path: str):
        """Fallback method to combine chunks using moviepy"""
        clips = []
        for chunk_path in chunk_paths:
            if os.path.exists(chunk_path):
                clip = VideoFileClip(chunk_path)
                clips.append(clip)

        if clips:
            final_clip = concatenate_videoclips(clips, method="compose")
            final_clip.write_videofile(
                output_path,
                fps=24,
                codec="libx264",
                audio_codec="aac",
                threads=4,
                preset="fast",
                ffmpeg_params=["-crf", "23", "-pix_fmt", "yuv420p"],
                verbose=False,
                logger=None
            )
            final_clip.close()

            for clip in clips:
                clip.close()

    async def _get_audio_duration(self, audio_path: str) -> float:
        """Get duration of audio file using FFprobe"""
        try:
            cmd = [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", audio_path
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                return float(stdout.decode().strip())
        except Exception as e:
            print(f"Error getting audio duration: {str(e)}")

        return 3.0  # Default duration

    async def _generate_audio_for_slide(self, transcript: str, slide_id: str,
                                        voice_speed: str, language: str) -> str:
        """Generate audio for a single slide and return the file path"""
        if not transcript.strip():
            return ""

        try:
            audio_data = await self.tts_provider.generate_speech(
                text=transcript,
                language=language,
                slow=(voice_speed == "slow")
            )

            # Save audio to temporary file
            temp_dir = tempfile.gettempdir()
            audio_path = os.path.join(temp_dir, f"{slide_id}_audio.mp3")

            with open(audio_path, "wb") as f:
                f.write(audio_data)

            self.temp_files.append(audio_path)
            return audio_path

        except Exception as e:
            print(f"Error generating audio for slide {slide_id}: {str(e)}")
            return ""

    def _cleanup_temp_files(self):
        """Clean up temporary files"""
        for file_path in self.temp_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"Error cleaning up file {file_path}: {str(e)}")

        self.temp_files = []
