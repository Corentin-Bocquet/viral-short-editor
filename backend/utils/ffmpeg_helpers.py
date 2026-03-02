"""FFmpeg helper functions for video processing."""
import json
import subprocess
import os
import shutil
from pathlib import Path
from typing import Dict, Any, Optional


def check_ffmpeg() -> bool:
    """Check if FFmpeg is installed and accessible."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def probe_video(video_path: str) -> Dict[str, Any]:
    """Probe video file to extract metadata using ffprobe.
    
    Args:
        video_path: Path to video file
        
    Returns:
        Dictionary with video metadata (width, height, duration, codec, etc.)
        
    Raises:
        RuntimeError: If ffprobe fails
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            video_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            check=True
        )
        
        data = json.loads(result.stdout)
        
        # Extract video stream info
        video_stream = next(
            (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
            None
        )
        
        if not video_stream:
            raise RuntimeError("No video stream found")
        
        audio_stream = next(
            (s for s in data.get("streams", []) if s.get("codec_type") == "audio"),
            None
        )
        
        return {
            "width": int(video_stream.get("width", 0)),
            "height": int(video_stream.get("height", 0)),
            "duration": float(data.get("format", {}).get("duration", 0)),
            "fps": eval(video_stream.get("r_frame_rate", "30/1")),
            "codec": video_stream.get("codec_name"),
            "has_audio": audio_stream is not None,
            "audio_codec": audio_stream.get("codec_name") if audio_stream else None,
        }
        
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffprobe failed: {e.stderr}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse ffprobe output: {e}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error during probe: {e}")


def run_ffmpeg(
    cmd: list,
    timeout: int = 600,
    progress_callback=None
) -> subprocess.CompletedProcess:
    """Run FFmpeg command with optional progress tracking.
    
    Args:
        cmd: FFmpeg command as list of strings
        timeout: Maximum execution time in seconds
        progress_callback: Optional callback function for progress updates
        
    Returns:
        CompletedProcess object
        
    Raises:
        RuntimeError: If FFmpeg command fails
    """
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        stderr_output = []
        
        # Read stderr line by line for progress
        for line in process.stderr:
            stderr_output.append(line)
            
            if progress_callback and "time=" in line:
                # Parse time from FFmpeg output
                try:
                    time_str = line.split("time=")[1].split()[0]
                    progress_callback(time_str)
                except (IndexError, ValueError):
                    pass
        
        process.wait(timeout=timeout)
        
        if process.returncode != 0:
            error_msg = "".join(stderr_output[-50:])  # Last 50 lines
            raise RuntimeError(f"FFmpeg failed (code {process.returncode}): {error_msg}")
        
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=process.returncode,
            stdout="",
            stderr="".join(stderr_output)
        )
        
    except subprocess.TimeoutExpired:
        process.kill()
        raise RuntimeError(f"FFmpeg command timed out after {timeout}s")
    except Exception as e:
        raise RuntimeError(f"FFmpeg execution error: {e}")


def cleanup_temp_dir(job_id: str) -> None:
    """Clean up temporary directory for a job.
    
    Args:
        job_id: Unique job identifier
    """
    temp_dir = Path(f"/tmp/viral_editor/{job_id}")
    
    if temp_dir.exists():
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            print(f"Warning: Failed to clean up {temp_dir}: {e}")


def create_work_dir(job_id: str) -> Path:
    """Create working directory for a job.
    
    Args:
        job_id: Unique job identifier
        
    Returns:
        Path to created directory
    """
    work_dir = Path(f"/tmp/viral_editor/{job_id}")
    work_dir.mkdir(parents=True, exist_ok=True)
    
    # Create subdirectories
    (work_dir / "brolls").mkdir(exist_ok=True)
    
    return work_dir


def get_video_aspect_ratio(width: int, height: int) -> tuple:
    """Calculate aspect ratio and determine if it's already 9:16.
    
    Args:
        width: Video width in pixels
        height: Video height in pixels
        
    Returns:
        Tuple of (ratio_width, ratio_height, is_9_16)
    """
    from math import gcd
    
    divisor = gcd(width, height)
    ratio_w = width // divisor
    ratio_h = height // divisor
    
    # Check if already 9:16 (with small tolerance)
    is_9_16 = abs((width / height) - (9 / 16)) < 0.01
    
    return (ratio_w, ratio_h, is_9_16)
