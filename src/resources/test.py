if True:
    import sys
    import os
    _src_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path[0] = os.path.dirname(_src_dir)

import asyncio
import subprocess
import shutil
import json
import tempfile
import os
import glob

import yt_dlp
import httpx
from google import genai
from google.genai import types as genai_types

from src.config import app_settings
from src.resources.utils import classify_youtube_url
from src.resources.types import YoutubeUrlType


def check_ffmpeg() -> bool:
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        print(f"ffmpeg found at: {ffmpeg_path}")
        return True
    
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=5,
        )
        if result.returncode == 0:
            print("ffmpeg found in PATH")
            return True
    except Exception:
        pass
    print("ffmpeg not available")
    return False

URLS = [
    # "https://www.youtube.com/playlist?list=PLNqp92_EXZBJRmV2ZKk_4rLgbd0MP-5r6",
    "https://www.youtube.com/@jherr",
]

RAW_INFO_JSON_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "yt_dlp_raw_info.json",
)


def get_yt_dlp_opts(yt_type: YoutubeUrlType) -> dict | None:
    base_opts = {
        "quiet": True,
        "skip_download": True,
        "socket_timeout": 30,
        "retries": 3,
        "geo_bypass": True,
    }
    video_opts = {
        **base_opts,
        "noplaylist": True,
    }
    playlist_opts = {
        **base_opts,
        "extract_flat": "in_playlist",
        "playlistend": 100,
        "ignoreerrors": True,
        "sleep_interval": 1,
        "max_sleep_interval": 3,
    }
    channel_opts = {
        **base_opts,
        "extract_flat": True,
        "playlistend": 0,
        "ignoreerrors": True,
    }

    return {
        YoutubeUrlType.SHORT: video_opts,
        YoutubeUrlType.VIDEO: video_opts,
        YoutubeUrlType.CHANNEL: channel_opts,
        YoutubeUrlType.PLAYLIST: playlist_opts,
        YoutubeUrlType.UNKNOWN: None,
    }.get(yt_type)

def fetch_metadata(urls):
    for url in urls:
        yt_type = classify_youtube_url(url)
        with yt_dlp.YoutubeDL(get_yt_dlp_opts(yt_type)) as ydl:
            info = ydl.extract_info(url)
            with open(RAW_INFO_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(info, f, indent=2, ensure_ascii=False, default=str)
            print(json.dumps(info, indent=2, ensure_ascii=False, default=str))
            print(f"Saved raw yt-dlp info to: {RAW_INFO_JSON_PATH}")
            print('============================================')
            return info
            
            
def download_video_lowest(urls) -> str | None:
    """Download the lowest-quality mp4 for each URL and return the path to the last downloaded file."""
    temp_dir = tempfile.mkdtemp(dir=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    print(f"Downloading to: {temp_dir}")

    ydl_opts = {
        'format': 'worstvideo[ext=mp4]',  # Lowest quality mp4
        'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
        'quiet': False,
    }

    downloaded_path: str | None = None
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for url in urls:
            ydl.download([url])
            print(f"Downloaded to: {temp_dir}")
            # Resolve the actual file that was written
            mp4_files = glob.glob(os.path.join(temp_dir, '*.mp4'))
            if mp4_files:
                downloaded_path = max(mp4_files, key=os.path.getmtime)

    return downloaded_path


async def sample_frames(video_path: str, frames_dir: str, fps: float = 1.0) -> list[str]:
    """Extract frames from *video_path* at *fps* frames per second using ffmpeg.

    Frames are saved as JPEGs inside *frames_dir*, which must already exist and
    is managed by the caller (e.g. via ``tempfile.TemporaryDirectory``).
    Returns the list of generated frame paths (sorted).

    These frames are intended to be sent to a vision model to generate short
    descriptions of the video content.
    """
    output_pattern = os.path.join(frames_dir, "frame_%04d.jpg")

    print(f"Sampling frames from: {video_path}")
    print(f"Output directory:     {frames_dir}")
    print(f"Frame rate:           {fps} fps")

    proc = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-i", video_path,
        "-vf", f"fps={fps}",
        "-vsync", "vfr",
        "-q:v", "2",           # JPEG quality (2 = near-lossless, 31 = worst)
        output_pattern,
        "-y",                  # overwrite without asking
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        error_msg = stderr.decode(errors="replace")
        raise RuntimeError(f"ffmpeg exited with code {proc.returncode}:\n{error_msg}")

    frame_paths = sorted(glob.glob(os.path.join(frames_dir, "frame_*.jpg")))
    print(f"Sampled {len(frame_paths)} frame(s) into: {frames_dir}")
    return frame_paths


FRAME_DESCRIPTION_PROMPT = (
    "Describe what is visible in this frame in 1-2 sentences. "
    "Focus on people, objects, text on screen, and setting."
)


async def describe_frame(client: genai.Client, frame_path: str) -> str:
    """Send a single JPEG frame to Gemini and return a short description."""
    with open(frame_path, "rb") as f:
        image_bytes = f.read()

    response = await client.aio.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=[
            genai_types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            FRAME_DESCRIPTION_PROMPT,
        ],
    )
    return response.text.strip()


async def main():
    # available = check_ffmpeg()
    # print(f"FFmpeg available: {available}")

    # video_path = download_video_lowest(URLS)

    # if video_path:
    #     client = genai.Client(api_key=app_settings.GEMINI_API_KEY)

    #     with tempfile.TemporaryDirectory(prefix="recall_frames_") as frames_dir:
    #         frames = await sample_frames(video_path, frames_dir, fps=1.0)
    #         print(f"\nSampled {len(frames)} frame(s). Describing first 10...\n")

    #         first_10 = frames[:10]
    #         descriptions = await asyncio.gather(
    #             *[describe_frame(client, fp) for fp in first_10]
    #         )

    #         for i, (fp, desc) in enumerate(zip(first_10, descriptions), start=1):
    #             print(f"[Frame {i:02d}] {os.path.basename(fp)}")
    #             print(f"  {desc}")
    #             print()
    # else:
    #     print("No video file found after download — skipping frame sampling.")

    # data = fetch_metadata(URLS)
    # print(get_video_transcript(data['id']))
    # for k,v in data.items():
    #     print(f"{k}:\n{v}\n")
    
    
    # redditurl = "https://www.reddit.com/r/indiameme/comments/1sqdv3l/this_needs_to_be_patented.json"
    
    with httpx.Client(follow_redirects=True) as client:
        response = client.head("https://youtu.be/rl_2ppGpPRA?si=iqXC-832oGzCv2ez", follow_redirects=True)
        print(response.url)
    


if __name__ == "__main__":
    asyncio.run(main())
