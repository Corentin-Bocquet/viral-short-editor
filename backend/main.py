"""FastAPI backend for Viral Short Editor."""
import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from processor.reframe import reframe_to_vertical, remove_silences
from processor.subtitles import (
    transcribe_audio,
    generate_ass_subtitles,
    generate_srt_subtitles,
    burn_subtitles,
    WHISPER_AVAILABLE
)
from processor.brolls import (
    extract_visual_concepts,
    fetch_broll,
    overlay_brolls,
    create_text_overlay_broll
)
from processor.audio_mix import mix_with_ducking
from utils.ffmpeg_helpers import check_ffmpeg, create_work_dir, cleanup_temp_dir


# Initialize FastAPI
app = FastAPI(
    title="Viral Short Editor API",
    description="Transform raw videos into viral 9:16 shorts",
    version="1.0.0"
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global job tracking
jobs: Dict[str, Dict[str, Any]] = {}


# Pydantic models
class JobStatus(BaseModel):
    job_id: str
    step: str
    progress: int
    message: str
    status: str  # "processing", "done", "error"
    error: Optional[str] = None


class ProcessRequest(BaseModel):
    music_volume: float = 0.10
    enable_brolls: bool = False


@app.on_event("startup")
async def startup_event():
    """Check dependencies on startup."""
    if not check_ffmpeg():
        print("ERROR: FFmpeg not found. Please install FFmpeg.")
        print("Visit: https://ffmpeg.org/download.html")
    
    if not WHISPER_AVAILABLE:
        print("Warning: Whisper not installed. Subtitle generation will be disabled.")
        print("Install with: pip install openai-whisper")
    
    print("✓ Viral Short Editor API started")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "app": "Viral Short Editor",
        "version": "1.0.0",
        "status": "running",
        "ffmpeg_available": check_ffmpeg(),
        "whisper_available": WHISPER_AVAILABLE
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


def update_job_progress(
    job_id: str,
    step: str,
    progress: int,
    message: str,
    status: str = "processing",
    error: Optional[str] = None
):
    """Update job progress in memory."""
    if job_id not in jobs:
        jobs[job_id] = {}
    
    jobs[job_id].update({
        "step": step,
        "progress": progress,
        "message": message,
        "status": status,
        "error": error,
        "updated_at": datetime.now().isoformat()
    })


async def process_video_task(
    job_id: str,
    video_path: Path,
    music_path: Optional[Path],
    music_volume: float,
    enable_brolls: bool
):
    """Background task to process video."""
    try:
        work_dir = create_work_dir(job_id)
        
        # ===== ÉTAPE A: Recadrage + Silence Removal (0-25%) =====
        update_job_progress(job_id, "A", 5, "Recadrage en format 9:16...")
        
        reframed_path = work_dir / "reframed.mp4"
        reframe_to_vertical(str(video_path), str(reframed_path))
        
        update_job_progress(job_id, "A", 15, "Suppression des silences (Jump Cuts)...")
        
        cut_path = work_dir / "cut.mp4"
        remove_silences(str(reframed_path), str(cut_path))
        
        update_job_progress(job_id, "A", 25, "✓ Nettoyage terminé")
        
        # ===== ÉTAPE B: Sous-titres (25-60%) =====
        if WHISPER_AVAILABLE:
            update_job_progress(job_id, "B", 30, "Transcription audio (Whisper)...")
            
            try:
                segments = transcribe_audio(str(cut_path), model_size="base")
                
                update_job_progress(
                    job_id, "B", 45,
                    f"{len(segments)} segments détectés, génération sous-titres..."
                )
                
                # Generate ASS (for burn-in)
                ass_path = work_dir / "subs.ass"
                generate_ass_subtitles(segments, str(ass_path))
                
                # Generate SRT (for export)
                srt_path = work_dir / "subs.srt"
                generate_srt_subtitles(segments, str(srt_path))
                
                # Store SRT path for later download
                jobs[job_id]["srt_path"] = str(srt_path)
                
                update_job_progress(job_id, "B", 55, "Incrustation des sous-titres...")
                
                subtitled_path = work_dir / "subtitled.mp4"
                burn_subtitles(str(cut_path), str(ass_path), str(subtitled_path))
                
                update_job_progress(job_id, "B", 60, "✓ Sous-titres incrustés")
                
            except Exception as e:
                print(f"Subtitle generation failed: {e}")
                update_job_progress(
                    job_id, "B", 60,
                    "⚠ Sous-titres désactivés (erreur Whisper)"
                )
                subtitled_path = cut_path
                segments = []
        else:
            update_job_progress(job_id, "B", 60, "⚠ Sous-titres désactivés (Whisper non installé)")
            subtitled_path = cut_path
            segments = []
        
        # ===== ÉTAPE C: B-Rolls (60-80%) =====
        if enable_brolls and segments:
            update_job_progress(job_id, "C", 65, "Analyse des concepts visuels...")
            
            concepts = extract_visual_concepts(segments, max_concepts=5)
            
            update_job_progress(
                job_id, "C", 70,
                f"{len(concepts)} concepts détectés, recherche B-rolls..."
            )
            
            # Fetch B-rolls
            broll_data = []
            brolls_dir = work_dir / "brolls"
            
            for i, concept_data in enumerate(concepts):
                concept = concept_data["query"]
                start_time = concept_data["timestamp_start"]
                
                # Try to fetch from Pexels
                broll_path = fetch_broll(concept, duration=2.0, output_dir=brolls_dir)
                
                if not broll_path:
                    # Fallback: text overlay
                    broll_path = str(brolls_dir / f"text_{i}.mp4")
                    create_text_overlay_broll(concept, 2.0, broll_path)
                
                if broll_path:
                    broll_data.append({
                        "path": broll_path,
                        "start": start_time,
                        "duration": 2.0
                    })
            
            if broll_data:
                update_job_progress(
                    job_id, "C", 75,
                    f"Insertion de {len(broll_data)} B-rolls..."
                )
                
                brolled_path = work_dir / "brolled.mp4"
                overlay_brolls(str(subtitled_path), broll_data, str(brolled_path))
                
                update_job_progress(job_id, "C", 80, f"✓ {len(broll_data)} B-rolls insérés")
            else:
                brolled_path = subtitled_path
                update_job_progress(job_id, "C", 80, "⚠ Aucun B-roll disponible")
        else:
            brolled_path = subtitled_path
            update_job_progress(
                job_id, "C", 80,
                "B-rolls désactivés" if not enable_brolls else "B-rolls ignorés (pas de transcription)"
            )
        
        # ===== ÉTAPE D: Mixage Audio (80-100%) =====
        update_job_progress(job_id, "D", 85, "Mixage audio + auto-ducking...")
        
        final_path = work_dir / "final.mp4"
        
        if music_path and music_path.exists():
            mix_with_ducking(
                str(brolled_path),
                str(music_path),
                str(final_path),
                music_volume=music_volume
            )
            update_job_progress(job_id, "D", 95, "✓ Musique mixée avec auto-ducking")
        else:
            # No music, just copy
            import shutil
            shutil.copy(str(brolled_path), str(final_path))
            update_job_progress(job_id, "D", 95, "✓ Audio conservé (pas de musique)")
        
        # Store final path
        jobs[job_id]["final_path"] = str(final_path)
        
        # Done!
        update_job_progress(job_id, "done", 100, "🎬 Vidéo prête !", status="done")
        
    except Exception as e:
        error_msg = str(e)
        print(f"Job {job_id} failed: {error_msg}")
        update_job_progress(
            job_id, "error", 0,
            f"Erreur: {error_msg}",
            status="error",
            error=error_msg
        )


@app.post("/api/process")
async def process_video(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    music: Optional[UploadFile] = File(None),
    music_volume: float = Form(0.10),
    enable_brolls: bool = Form(False)
):
    """Start video processing job."""
    # Generate job ID
    job_id = str(uuid.uuid4())
    
    # Create work directory
    work_dir = create_work_dir(job_id)
    
    # Save uploaded video
    video_path = work_dir / f"input{Path(video.filename).suffix}"
    with open(video_path, "wb") as f:
        content = await video.read()
        f.write(content)
    
    # Save music if provided
    music_path = None
    if music and music.filename:
        music_path = work_dir / f"music{Path(music.filename).suffix}"
        with open(music_path, "wb") as f:
            content = await music.read()
            f.write(content)
    
    # Initialize job
    jobs[job_id] = {
        "job_id": job_id,
        "status": "processing",
        "step": "init",
        "progress": 0,
        "message": "Job créé",
        "created_at": datetime.now().isoformat()
    }
    
    # Start background processing
    background_tasks.add_task(
        process_video_task,
        job_id,
        video_path,
        music_path,
        music_volume,
        enable_brolls
    )
    
    return {"job_id": job_id}


@app.get("/api/progress/{job_id}")
async def get_progress(job_id: str):
    """Stream job progress via Server-Sent Events (SSE)."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    async def event_stream():
        """Generate SSE events for progress."""
        while True:
            if job_id in jobs:
                job_data = jobs[job_id]
                
                # Send progress event
                event_data = json.dumps({
                    "step": job_data.get("step", "init"),
                    "progress": job_data.get("progress", 0),
                    "message": job_data.get("message", ""),
                    "status": job_data.get("status", "processing"),
                    "error": job_data.get("error")
                })
                
                yield f"data: {event_data}\n\n"
                
                # Stop streaming if done or error
                if job_data.get("status") in ["done", "error"]:
                    break
            
            await asyncio.sleep(0.5)  # Poll every 500ms
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/api/result/{job_id}")
async def get_result(job_id: str):
    """Download final processed video."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_data = jobs[job_id]
    
    if job_data.get("status") != "done":
        raise HTTPException(status_code=400, detail="Job not completed yet")
    
    final_path = job_data.get("final_path")
    
    if not final_path or not Path(final_path).exists():
        raise HTTPException(status_code=404, detail="Result file not found")
    
    return FileResponse(
        final_path,
        media_type="video/mp4",
        filename="viral_short.mp4"
    )


@app.get("/api/subtitles/{job_id}")
async def get_subtitles(job_id: str):
    """Download SRT subtitle file."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_data = jobs[job_id]
    srt_path = job_data.get("srt_path")
    
    if not srt_path or not Path(srt_path).exists():
        raise HTTPException(status_code=404, detail="Subtitle file not found")
    
    return FileResponse(
        srt_path,
        media_type="text/plain",
        filename="subtitles.srt"
    )


@app.delete("/api/cleanup/{job_id}")
async def cleanup_job(job_id: str):
    """Clean up temporary files for a job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Cleanup temp directory
    cleanup_temp_dir(job_id)
    
    # Remove from jobs dict
    del jobs[job_id]
    
    return {"message": "Job cleaned up"}


@app.get("/api/jobs")
async def list_jobs():
    """List all active jobs (for debugging)."""
    return {
        "total": len(jobs),
        "jobs": [
            {
                "job_id": job_id,
                "status": data.get("status"),
                "progress": data.get("progress"),
                "created_at": data.get("created_at")
            }
            for job_id, data in jobs.items()
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
