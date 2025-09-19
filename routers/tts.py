import json
import os
from fastapi.responses import JSONResponse
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, status

# Add these global variables for job tracking
job_statuses = {}
JOB_RESULTS_DIR = os.path.join(os.getcwd(), "job_results")
os.makedirs(JOB_RESULTS_DIR, exist_ok=True)
router = APIRouter()

# Add this function to save job status


def save_job_status(job_id: str, status: dict):
    """Save job status to a file"""
    status_file = os.path.join(JOB_RESULTS_DIR, f"{job_id}.json")
    with open(status_file, "w") as f:
        json.dump(status, f)

# Add this function to load job status


def load_job_status(job_id: str) -> dict:
    """Load job status from a file"""
    status_file = os.path.join(JOB_RESULTS_DIR, f"{job_id}.json")
    if os.path.exists(status_file):
        with open(status_file, "r") as f:
            return json.load(f)
    return {"status": "unknown", "message": "Job not found"}

# Replace your process_pptx function with this:


@router.post("/process-pptx")
async def process_pptx(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    voice_speed: str = "normal",
    language: str = "en"
):
    """
    Processes a PowerPoint file to generate a video with voiceovers in background.
    """
    print("=== Starting PPTX processing ===")
    tmp_path = None

    try:
        # Check file size manually
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)

        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB"
            )

        # Check file type
        if not file.filename.lower().endswith('.pptx'):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Only PPTX files are supported"
            )

        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pptx") as tmp_file:
            shutil.copyfileobj(file.file, tmp_file)
            tmp_path = tmp_file.name

        # Validate PPTX file
        if not pptx_processor.validate_pptx_file(tmp_path):
            raise HTTPException(status_code=400, detail="Invalid PPTX file")

        # Generate a unique job ID
        job_id = f"aventra_{int(time.time())}"

        # Save initial job status
        job_status = {
            "status": "processing",
            "message": "Starting processing",
            "progress": 0,
            "job_id": job_id
        }
        save_job_status(job_id, job_status)

        # Add to background tasks
        background_tasks.add_task(
            process_pptx_background,
            tmp_path, job_id, voice_speed, language
        )

        return JSONResponse(
            status_code=202,  # Accepted
            content=job_status
        )

    except HTTPException:
        raise
    except Exception as e:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise HTTPException(
            status_code=500, detail=f"Error starting processing: {str(e)}")

# Add this background processing function


async def process_pptx_background(tmp_path: str, job_id: str,
                                  voice_speed: str, language: str):
    """Background task to process PPTX"""
    try:
        # Update job status
        job_status = {
            "status": "processing",
            "message": "Extracting text from slides",
            "progress": 10,
            "job_id": job_id
        }
        save_job_status(job_id, job_status)

        # Extract text from slides
        slide_texts = pptx_processor.extract_text_from_pptx(tmp_path)

        job_status.update({
            "message": "Generating transcripts with AI",
            "progress": 30
        })
        save_job_status(job_id, job_status)

        # Generate transcripts using LLM
        transcripts = await llm_integration.generate_transcript(slide_texts)

        job_status.update({
            "message": "Extracting slide images",
            "progress": 50
        })
        save_job_status(job_id, job_status)

        # Extract slide images
        with tempfile.TemporaryDirectory() as temp_dir:
            slide_images = pptx_processor.extract_slide_images(
                tmp_path, temp_dir)

            job_status.update({
                "message": "Generating video with voiceovers",
                "progress": 70
            })
            save_job_status(job_id, job_status)

            # Generate video with voiceovers
            output_filename = f"{job_id}.mp4"
            video_path = await video_generator.create_video(
                slide_images, transcripts, output_filename, voice_speed, language
            )

            # Final job status
            job_status.update({
                "status": "completed",
                "message": "Video generation complete",
                "progress": 100,
                "video_path": video_path,
                "download_url": f"/api/tts/download/{job_id}"
            })
            save_job_status(job_id, job_status)

        print(f"=== PPTX processing completed for job {job_id} ===")

    except Exception as e:
        error_details = traceback.format_exc()
        print(f"Error processing PPTX in background: {str(e)}")
        print(f"Traceback: {error_details}")

        # Update job status with error
        job_status = {
            "status": "error",
            "message": f"Error processing PPTX: {str(e)}",
            "progress": 0,
            "job_id": job_id
        }
        save_job_status(job_id, job_status)

    finally:
        # Clean up temporary files
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

# Add this endpoint to check job status


@router.get("/job-status/{job_id}")
async def get_job_status(job_id: str):
    """Check the status of a processing job"""
    job_status = load_job_status(job_id)
    return job_status

# Add this endpoint to download the result


@router.get("/download/{job_id}")
async def download_video(job_id: str):
    """Download the generated video"""
    job_status = load_job_status(job_id)

    if job_status.get("status") != "completed" or "video_path" not in job_status:
        raise HTTPException(status_code=404, detail="Video not available")

    video_path = job_status["video_path"]

    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found")

    return FileResponse(
        path=video_path,
        media_type="video/mp4",
        filename=f"{job_id}.mp4"
    )
