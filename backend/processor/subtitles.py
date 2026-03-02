"""Module B: Transcription with Whisper and subtitle generation with karaoke effects."""
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import timedelta

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    print("Warning: openai-whisper not installed. Subtitle generation will be disabled.")

from ..utils.nlp_keywords import classify_word, get_emoji_for_text, should_insert_emoji
from ..utils.ffmpeg_helpers import run_ffmpeg


# ASS color mapping (BGR format in hex)
COLOR_MAP = {
    "white": "&H00FFFFFF",
    "red": "&H000063FF",      # BGR: Blue=00, Green=00, Red=63
    "green": "&H0000FF00",    # BGR: Blue=00, Green=FF, Red=00  
    "yellow": "&H0000FFFF",   # BGR: Blue=00, Green=FF, Red=FF
}


def extract_audio(video_path: str, output_path: str) -> str:
    """Extract audio from video for transcription.
    
    Args:
        video_path: Path to video file
        output_path: Path for output audio file (WAV)
        
    Returns:
        Path to extracted audio
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",  # No video
        "-ar", "16000",  # 16kHz sample rate for Whisper
        "-ac", "1",  # Mono
        "-c:a", "pcm_s16le",  # 16-bit PCM
        output_path
    ]
    
    run_ffmpeg(cmd)
    return output_path


def transcribe_audio(
    video_path: str,
    model_size: str = "base",
    language: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Transcribe audio using OpenAI Whisper.
    
    Args:
        video_path: Path to video file
        model_size: Whisper model size (tiny/base/small/medium/large)
        language: Language code (None for auto-detection)
        
    Returns:
        List of segment dictionaries with word-level timestamps
        
    Raises:
        RuntimeError: If transcription fails
    """
    if not WHISPER_AVAILABLE:
        raise RuntimeError(
            "Whisper not installed. Install with: pip install openai-whisper"
        )
    
    try:
        # Extract audio
        work_dir = Path(video_path).parent
        audio_path = work_dir / "audio.wav"
        extract_audio(video_path, str(audio_path))
        
        # Load Whisper model
        print(f"Loading Whisper model '{model_size}'...")
        model = whisper.load_model(model_size)
        
        # Transcribe with word timestamps
        print("Transcribing audio...")
        result = model.transcribe(
            str(audio_path),
            language=language,
            word_timestamps=True,
            verbose=False
        )
        
        # Cleanup audio file
        audio_path.unlink(missing_ok=True)
        
        # Return segments with word-level info
        return result.get("segments", [])
        
    except Exception as e:
        raise RuntimeError(f"Transcription failed: {e}")


def format_ass_time(seconds: float) -> str:
    """Format time for ASS subtitle format (h:mm:ss.cc).
    
    Args:
        seconds: Time in seconds
        
    Returns:
        Formatted time string
    """
    td = timedelta(seconds=seconds)
    hours = int(td.total_seconds() // 3600)
    minutes = int((td.total_seconds() % 3600) // 60)
    secs = int(td.total_seconds() % 60)
    centisecs = int((td.total_seconds() % 1) * 100)
    
    return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"


def generate_ass_subtitles(
    segments: List[Dict[str, Any]],
    output_path: str
) -> str:
    """Generate ASS subtitle file with karaoke effects and color coding.
    
    Args:
        segments: Whisper transcription segments with word timestamps
        output_path: Path for output ASS file
        
    Returns:
        Path to generated ASS file
    """
    # ASS file header
    ass_content = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Impact,85,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,0,2,20,20,250,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    
    events = []
    segment_count = 0
    
    for segment in segments:
        # Get words from segment
        words = segment.get("words", [])
        
        if not words:
            # Fallback to segment-level timing if no word timestamps
            text = segment.get("text", "").strip()
            if not text:
                continue
                
            start_time = format_ass_time(segment["start"])
            end_time = format_ass_time(segment["end"])
            
            # Simple subtitle without karaoke
            events.append(
                f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text}"
            )
            continue
        
        # Process word by word for karaoke effect
        for i, word_data in enumerate(words):
            word = word_data.get("word", "").strip()
            if not word:
                continue
            
            start = word_data.get("start", 0)
            end = word_data.get("end", start + 0.5)
            duration_cs = int((end - start) * 100)  # Duration in centiseconds
            
            # Classify word color
            color = classify_word(word)
            ass_color = COLOR_MAP.get(color, COLOR_MAP["white"])
            
            start_time = format_ass_time(start)
            end_time = format_ass_time(end)
            
            # Karaoke effect: word grows slightly when spoken
            # {\k<duration>} for karaoke fill
            # {\fscx110\fscy110} for 110% scale
            karaoke_tag = f"{{\\k{duration_cs}}}{{\\fscx110\\fscy110}}"
            
            # Apply color override if not white
            if color != "white":
                color_tag = f"{{\\c{ass_color}}}"
                text = f"{color_tag}{karaoke_tag}{word}"
            else:
                text = f"{karaoke_tag}{word}"
            
            events.append(
                f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text}"
            )
        
        # Insert emoji every 4 segments
        segment_count += 1
        if should_insert_emoji(segment_count, len(segments)):
            segment_text = segment.get("text", "")
            emoji = get_emoji_for_text(segment_text)
            
            if emoji:
                # Add emoji at the end of this segment
                last_word = words[-1]
                start_time = format_ass_time(last_word.get("end", segment["end"]))
                end_time = format_ass_time(segment["end"] + 0.5)
                
                events.append(
                    f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{{\\fs100}}{emoji}"
                )
    
    # Combine header and events
    ass_content += "\n".join(events)
    
    # Write to file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(ass_content)
    
    print(f"Generated ASS subtitles: {len(events)} entries")
    return output_path


def generate_srt_subtitles(
    segments: List[Dict[str, Any]],
    output_path: str
) -> str:
    """Generate SRT subtitle file (simple format for export).
    
    Args:
        segments: Whisper transcription segments
        output_path: Path for output SRT file
        
    Returns:
        Path to generated SRT file
    """
    def format_srt_time(seconds: float) -> str:
        """Format time for SRT (hh:mm:ss,ms)."""
        td = timedelta(seconds=seconds)
        hours = int(td.total_seconds() // 3600)
        minutes = int((td.total_seconds() % 3600) // 60)
        secs = int(td.total_seconds() % 60)
        ms = int((td.total_seconds() % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"
    
    srt_content = []
    
    for i, segment in enumerate(segments, 1):
        text = segment.get("text", "").strip()
        if not text:
            continue
        
        start_time = format_srt_time(segment["start"])
        end_time = format_srt_time(segment["end"])
        
        srt_content.append(f"{i}")
        srt_content.append(f"{start_time} --> {end_time}")
        srt_content.append(text)
        srt_content.append("")  # Blank line
    
    # Write to file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(srt_content))
    
    return output_path


def burn_subtitles(
    video_path: str,
    ass_path: str,
    output_path: str
) -> str:
    """Burn ASS subtitles into video.
    
    Args:
        video_path: Path to input video
        ass_path: Path to ASS subtitle file
        output_path: Path for output video
        
    Returns:
        Path to output video with burned subtitles
    """
    # Escape Windows paths for FFmpeg
    ass_path_escaped = ass_path.replace('\\', '/').replace(':', '\\\\:')
    
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", f"ass={ass_path_escaped}",
        "-c:v", "libx264",
        "-crf", "23",
        "-preset", "fast",
        "-c:a", "copy",
        output_path
    ]
    
    run_ffmpeg(cmd)
    return output_path
