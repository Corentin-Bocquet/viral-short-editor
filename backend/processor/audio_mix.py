"""Module D: Audio mixing with auto-ducking (music volume reduces when voice is active)."""
from pathlib import Path
from ..utils.ffmpeg_helpers import run_ffmpeg, probe_video


def mix_with_ducking(
    video_path: str,
    music_path: str,
    output_path: str,
    music_volume: float = 0.10
) -> str:
    """Mix video audio with background music using auto-ducking.
    
    Auto-ducking: Music volume is reduced when voice is present.
    
    Args:
        video_path: Path to video with voice audio
        music_path: Path to music file (optional, can be None/empty)
        output_path: Path for output video
        music_volume: Base music volume (0.0 to 1.0, default 0.10)
        
    Returns:
        Path to output video with mixed audio
    """
    # If no music, just copy the video
    if not music_path or not Path(music_path).exists():
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-c", "copy",
            output_path
        ]
        run_ffmpeg(cmd)
        return output_path
    
    # Get video duration to loop music if needed
    metadata = probe_video(video_path)
    video_duration = metadata["duration"]
    
    # Complex filter for auto-ducking
    # sidechaincompress: when voice is detected, compress (reduce) music
    
    filter_complex = f"""
        [1:a]aloop=loop=-1:size=2e+09[music_loop];
        [music_loop]volume={music_volume}[music_vol];
        [0:a][music_vol]sidechaincompress=threshold=0.02:ratio=4:attack=200:release=1000[mixed]
    """
    
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", music_path,
        "-filter_complex", filter_complex,
        "-map", "0:v",  # Video from input 0
        "-map", "[mixed]",  # Mixed audio
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-t", str(video_duration),  # Trim to video duration
        output_path
    ]
    
    run_ffmpeg(cmd)
    return output_path


def mix_without_ducking(
    video_path: str,
    music_path: str,
    output_path: str,
    music_volume: float = 0.10,
    voice_volume: float = 1.0
) -> str:
    """Mix video audio with background music (simple mixing, no ducking).
    
    Args:
        video_path: Path to video with voice audio
        music_path: Path to music file
        output_path: Path for output video
        music_volume: Music volume (0.0 to 1.0)
        voice_volume: Voice volume (0.0 to 1.0)
        
    Returns:
        Path to output video
    """
    if not music_path or not Path(music_path).exists():
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-c", "copy",
            output_path
        ]
        run_ffmpeg(cmd)
        return output_path
    
    metadata = probe_video(video_path)
    video_duration = metadata["duration"]
    
    filter_complex = f"""
        [1:a]aloop=loop=-1:size=2e+09,volume={music_volume}[music];
        [0:a]volume={voice_volume}[voice];
        [voice][music]amix=inputs=2:duration=first[mixed]
    """
    
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", music_path,
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[mixed]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-t", str(video_duration),
        output_path
    ]
    
    run_ffmpeg(cmd)
    return output_path
