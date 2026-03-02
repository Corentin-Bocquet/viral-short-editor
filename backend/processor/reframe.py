"""Module A: Video reframing to 9:16 and silence removal for jump cuts."""
import subprocess
import re
from pathlib import Path
from typing import List, Tuple
from ..utils.ffmpeg_helpers import probe_video, run_ffmpeg, get_video_aspect_ratio


def reframe_to_vertical(input_path: str, output_path: str) -> str:
    """Reframe video to vertical 9:16 format (1080x1920).
    
    Args:
        input_path: Path to input video
        output_path: Path to output video
        
    Returns:
        Path to output video
        
    Raises:
        RuntimeError: If reframing fails
    """
    # Probe video to get dimensions
    metadata = probe_video(input_path)
    width = metadata["width"]
    height = metadata["height"]
    
    # Check if already 9:16
    _, _, is_9_16 = get_video_aspect_ratio(width, height)
    
    if is_9_16:
        # Already correct aspect ratio, just ensure 1080x1920 resolution
        if width == 1080 and height == 1920:
            # Perfect, just copy
            cmd = [
                "ffmpeg", "-y",
                "-i", input_path,
                "-c", "copy",
                output_path
            ]
        else:
            # Scale to 1080x1920
            cmd = [
                "ffmpeg", "-y",
                "-i", input_path,
                "-vf", "scale=1080:1920",
                "-c:v", "libx264",
                "-crf", "23",
                "-preset", "fast",
                "-c:a", "copy",
                output_path
            ]
    else:
        # Need to crop to 9:16
        # Calculate crop dimensions
        target_ratio = 9 / 16
        current_ratio = width / height
        
        if current_ratio > target_ratio:
            # Video is too wide, crop horizontally
            new_width = int(height * target_ratio)
            crop_x = (width - new_width) // 2
            crop_filter = f"crop={new_width}:{height}:{crop_x}:0"
        else:
            # Video is too tall, crop vertically  
            new_height = int(width / target_ratio)
            crop_y = (height - new_height) // 2
            crop_filter = f"crop={width}:{new_height}:0:{crop_y}"
        
        # Crop and scale to 1080x1920
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vf", f"{crop_filter},scale=1080:1920",
            "-c:v", "libx264",
            "-crf", "23",
            "-preset", "fast",
            "-c:a", "copy",
            output_path
        ]
    
    # Run FFmpeg
    run_ffmpeg(cmd)
    
    return output_path


def detect_silences(
    input_path: str,
    threshold_db: float = -35.0,
    min_silence_ms: int = 200
) -> List[Tuple[float, float]]:
    """Detect silence segments in video.
    
    Args:
        input_path: Path to video file
        threshold_db: Silence threshold in dB (default -35)
        min_silence_ms: Minimum silence duration in milliseconds (default 200)
        
    Returns:
        List of (start_time, end_time) tuples for each silence segment
    """
    # Convert ms to seconds for FFmpeg
    min_silence_s = min_silence_ms / 1000.0
    
    cmd = [
        "ffmpeg",
        "-i", input_path,
        "-af", f"silencedetect=n={threshold_db}dB:d={min_silence_s}",
        "-f", "null",
        "-"
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        stderr = result.stderr
        
        # Parse silence detection output
        # Format: [silencedetect @ ...] silence_start: 1.234
        #         [silencedetect @ ...] silence_end: 2.345 | silence_duration: 1.111
        
        silence_starts = []
        silence_ends = []
        
        for line in stderr.split('\n'):
            if 'silence_start:' in line:
                match = re.search(r'silence_start: ([\d.]+)', line)
                if match:
                    silence_starts.append(float(match.group(1)))
            elif 'silence_end:' in line:
                match = re.search(r'silence_end: ([\d.]+)', line)
                if match:
                    silence_ends.append(float(match.group(1)))
        
        # Pair starts with ends
        silences = []
        for start, end in zip(silence_starts, silence_ends):
            silences.append((start, end))
        
        return silences
        
    except subprocess.TimeoutExpired:
        raise RuntimeError("Silence detection timed out")
    except Exception as e:
        raise RuntimeError(f"Silence detection failed: {e}")


def remove_silences(
    input_path: str,
    output_path: str,
    threshold_db: float = -35.0,
    min_silence_ms: int = 200
) -> str:
    """Remove silence segments from video to create jump cuts.
    
    Args:
        input_path: Path to input video
        output_path: Path to output video
        threshold_db: Silence threshold in dB
        min_silence_ms: Minimum silence duration in milliseconds
        
    Returns:
        Path to output video
    """
    # Detect silences
    silences = detect_silences(input_path, threshold_db, min_silence_ms)
    
    if not silences:
        # No silences detected, just copy the file
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-c", "copy",
            output_path
        ]
        run_ffmpeg(cmd)
        print(f"No silences detected (threshold={threshold_db}dB, min={min_silence_ms}ms)")
        return output_path
    
    # Get video duration
    metadata = probe_video(input_path)
    duration = metadata["duration"]
    
    # Build segments (non-silent parts)
    segments = []
    prev_end = 0.0
    
    for silence_start, silence_end in silences:
        if silence_start > prev_end:
            # Add the speaking segment before this silence
            segments.append((prev_end, silence_start))
        prev_end = silence_end
    
    # Add final segment if exists
    if prev_end < duration:
        segments.append((prev_end, duration))
    
    if not segments:
        # Edge case: entire video is silence
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-c", "copy",
            output_path
        ]
        run_ffmpeg(cmd)
        return output_path
    
    # Create segment files
    work_dir = Path(output_path).parent
    segment_paths = []
    
    for i, (start, end) in enumerate(segments):
        segment_path = work_dir / f"segment_{i:04d}.mp4"
        
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-ss", str(start),
            "-to", str(end),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            str(segment_path)
        ]
        
        run_ffmpeg(cmd)
        segment_paths.append(segment_path)
    
    # Create concat file
    concat_file = work_dir / "concat_list.txt"
    with open(concat_file, 'w') as f:
        for segment_path in segment_paths:
            f.write(f"file '{segment_path.name}'\n")
    
    # Concatenate segments
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        output_path
    ]
    
    run_ffmpeg(cmd)
    
    # Cleanup segment files
    for segment_path in segment_paths:
        segment_path.unlink(missing_ok=True)
    concat_file.unlink(missing_ok=True)
    
    # Calculate time saved
    total_silence_duration = sum(end - start for start, end in silences)
    print(f"Removed {len(silences)} silence segments, saved {total_silence_duration:.2f}s")
    
    return output_path
