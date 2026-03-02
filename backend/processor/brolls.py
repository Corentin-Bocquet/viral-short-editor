"""Module C: B-roll extraction and overlay using Pexels API."""
import os
import re
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional
from ..utils.ffmpeg_helpers import run_ffmpeg


# Get API key from environment
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")


# Words to filter out (not filmable)
STOPWORDS = {
    # French
    "je", "tu", "il", "elle", "nous", "vous", "ils", "elles",
    "le", "la", "les", "un", "une", "des", "ce", "cette", "ces",
    "mon", "ma", "mes", "ton", "ta", "tes", "son", "sa", "ses",
    "notre", "votre", "leur", "de", "du", "au", "à", "en", "dans",
    "pour", "par", "avec", "sans", "sur", "sous", "qui", "que",
    "quoi", "dont", "où", "et", "ou", "mais", "donc", "car",
    "si", "comme", "quand", "est", "sont", "avoir", "être",
    "faire", "dire", "voir", "aller", "venir", "pouvoir",
    # English
    "i", "you", "he", "she", "we", "they", "the", "a", "an",
    "this", "that", "these", "those", "my", "your", "his", "her",
    "our", "their", "of", "to", "in", "for", "with", "on", "at",
    "from", "by", "about", "as", "into", "like", "through",
    "after", "over", "between", "out", "against", "during",
    "without", "before", "under", "around", "among",
    "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "must", "can",
}


def extract_visual_concepts(
    segments: List[Dict[str, Any]],
    max_concepts: int = 5
) -> List[Dict[str, Any]]:
    """Extract filmable visual concepts from transcription segments.
    
    Args:
        segments: Whisper transcription segments
        max_concepts: Maximum number of concepts to extract
        
    Returns:
        List of concept dictionaries with timestamp and query
    """
    concepts = []
    
    for segment in segments:
        text = segment.get("text", "").lower()
        start = segment.get("start", 0)
        end = segment.get("end", start + 3)
        
        # Extract words (remove punctuation)
        words = re.findall(r'\b[a-zà-ÿ]+\b', text)
        
        # Filter filmable concepts (nouns, action verbs)
        filmable = []
        for word in words:
            # Skip stopwords and very short words
            if word in STOPWORDS or len(word) < 4:
                continue
            
            filmable.append(word)
        
        # Take most relevant word as concept (first meaningful word)
        if filmable:
            concept = filmable[0]
            
            concepts.append({
                "timestamp_start": start,
                "timestamp_end": min(start + 2.0, end),  # Max 2s B-roll
                "concept": concept,
                "query": concept,
                "text_context": text[:50]  # Keep context for debugging
            })
        
        # Limit to max_concepts
        if len(concepts) >= max_concepts:
            break
    
    return concepts


def fetch_broll(
    concept: str,
    duration: float = 2.0,
    output_dir: Path = Path("/tmp")
) -> Optional[str]:
    """Fetch B-roll video from Pexels API.
    
    Args:
        concept: Search query concept
        duration: Desired duration in seconds (will be trimmed)
        output_dir: Directory to save downloaded video
        
    Returns:
        Path to downloaded and trimmed B-roll, or None if failed
    """
    if not PEXELS_API_KEY:
        print("Warning: PEXELS_API_KEY not set. Cannot fetch B-rolls.")
        return None
    
    try:
        # Search Pexels API
        url = "https://api.pexels.com/videos/search"
        headers = {
            "Authorization": PEXELS_API_KEY
        }
        params = {
            "query": concept,
            "per_page": 3,
            "size": "medium",  # or "large" for HD
            "orientation": "portrait"  # Prefer vertical
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        videos = data.get("videos", [])
        
        if not videos:
            print(f"No B-roll found for concept: {concept}")
            return None
        
        # Get first video with HD quality
        video = videos[0]
        video_files = video.get("video_files", [])
        
        # Find HD file (width >= 1080)
        hd_file = None
        for vf in video_files:
            if vf.get("width", 0) >= 1080:
                hd_file = vf
                break
        
        if not hd_file:
            # Fallback to first available
            hd_file = video_files[0] if video_files else None
        
        if not hd_file:
            print(f"No video file found for concept: {concept}")
            return None
        
        video_url = hd_file.get("link")
        if not video_url:
            return None
        
        # Download video
        output_path = output_dir / f"broll_{concept[:20]}.mp4"
        
        print(f"Downloading B-roll for '{concept}'...")
        video_response = requests.get(video_url, timeout=30)
        video_response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            f.write(video_response.content)
        
        # Trim to exact duration
        trimmed_path = output_dir / f"broll_{concept[:20]}_cut.mp4"
        
        cmd = [
            "ffmpeg", "-y",
            "-i", str(output_path),
            "-t", str(duration),
            "-c", "copy",
            str(trimmed_path)
        ]
        
        run_ffmpeg(cmd)
        
        # Remove original
        output_path.unlink(missing_ok=True)
        
        return str(trimmed_path)
        
    except requests.RequestException as e:
        print(f"Failed to fetch B-roll for '{concept}': {e}")
        return None
    except Exception as e:
        print(f"Unexpected error fetching B-roll: {e}")
        return None


def create_text_overlay_broll(
    concept: str,
    duration: float,
    output_path: str
) -> str:
    """Create a simple text overlay B-roll as fallback.
    
    Args:
        concept: Text to display
        duration: Duration in seconds
        output_path: Path for output video
        
    Returns:
        Path to generated video
    """
    # Create a black video with text overlay
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c=black:s=1080x1920:d={duration}",
        "-vf", f"drawtext=text='{concept}':fontcolor=white:fontsize=100:x=(w-text_w)/2:y=(h-text_h)/2",
        "-c:v", "libx264",
        "-t", str(duration),
        "-pix_fmt", "yuv420p",
        output_path
    ]
    
    run_ffmpeg(cmd)
    return output_path


def overlay_brolls(
    aroll_path: str,
    broll_list: List[Dict[str, Any]],
    output_path: str
) -> str:
    """Overlay B-rolls on top of A-roll at specified timestamps.
    
    Args:
        aroll_path: Path to A-roll video (main video)
        broll_list: List of B-roll dicts with 'path', 'start', 'duration'
        output_path: Path for output video
        
    Returns:
        Path to output video with B-rolls overlaid
    """
    if not broll_list:
        # No B-rolls, just copy
        cmd = [
            "ffmpeg", "-y",
            "-i", aroll_path,
            "-c", "copy",
            output_path
        ]
        run_ffmpeg(cmd)
        return output_path
    
    # Build complex filter for overlaying B-rolls
    # Each B-roll needs to be scaled to 1080x1920 and overlaid at specific time
    
    filter_complex = []
    overlay_chain = "0:v"  # Start with A-roll video
    
    for i, broll in enumerate(broll_list):
        broll_path = broll.get("path")
        start_time = broll.get("start", 0)
        
        if not broll_path or not Path(broll_path).exists():
            continue
        
        # Scale B-roll to 1080x1920
        filter_complex.append(
            f"[{i+1}:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
            f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2[broll{i}]"
        )
        
        # Overlay at specific time (hard cut)
        filter_complex.append(
            f"[{overlay_chain}][broll{i}]overlay=enable='between(t,{start_time},{start_time+2})':x=0:y=0[v{i}]"
        )
        
        overlay_chain = f"v{i}"
    
    # Build FFmpeg command with multiple inputs
    cmd = ["ffmpeg", "-y", "-i", aroll_path]
    
    for broll in broll_list:
        broll_path = broll.get("path")
        if broll_path and Path(broll_path).exists():
            cmd.extend(["-i", broll_path])
    
    # Add filter complex
    cmd.extend([
        "-filter_complex", ";".join(filter_complex),
        "-map", f"[{overlay_chain}]",
        "-map", "0:a",  # Keep original audio
        "-c:v", "libx264",
        "-crf", "23",
        "-preset", "fast",
        "-c:a", "copy",
        output_path
    ])
    
    run_ffmpeg(cmd)
    return output_path
