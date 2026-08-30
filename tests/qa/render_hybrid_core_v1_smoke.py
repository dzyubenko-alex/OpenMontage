"""Generate disposable video clips, render mixed HYBRID media, and verify MP4."""
from __future__ import annotations
import json
import subprocess
from pathlib import Path
from tools.video.video_compose import VideoCompose

ROOT = Path(__file__).resolve().parents[2]
PROPS_PATH = ROOT / "tests/fixtures/hybrid_core_v1_smoke/props.json"
FIXTURES = ROOT / "output/hybrid-core-v1-smoke-fixtures"
OUTPUT = ROOT / "output/hybrid-core-v1-smoke.mp4"

def make_clip(path: Path, color: str, frequency: int) -> None:
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", f"color=c={color}:s=640x360:r=30:d=5",
        "-f", "lavfi", "-i", f"sine=frequency={frequency}:sample_rate=48000:duration=5",
        "-vf", "drawgrid=width=64:height=64:thickness=3:color=white@0.35",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path),
    ], check=True)

def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for photo in ("photo-a.svg", "photo-b.svg"):
        target = FIXTURES / photo
        target.write_bytes((PROPS_PATH.parent / photo).read_bytes())
    make_clip(FIXTURES / "video-a.mp4", "0x17324d", 330)
    make_clip(FIXTURES / "video-b.mp4", "0x7a2848", 440)
    props = json.loads(PROPS_PATH.read_text())
    assert {cut["media_type"] for cut in props["cuts"]} == {"photo", "video"}
    assert props["profiles"]["voice"]["enabled"] is False
    assert props["profiles"]["music"]["enabled"] is False
    assert props["profiles"]["branding"]["enabled"] is False
    result = VideoCompose().execute({
        "operation": "remotion_render", "composition_data": props,
        "public_dir": str(FIXTURES), "output_path": str(OUTPUT),
        "remotion_timeout_ms": 120_000, "browser_executable": "/usr/bin/google-chrome-stable",
    })
    if not result.success:
        raise RuntimeError(result.error)
    probe = subprocess.run([
        "ffprobe", "-v", "error",
        "-show_entries", "stream=codec_type,width,height,r_frame_rate:format=duration",
        "-of", "json", str(OUTPUT),
    ], check=True, capture_output=True, text=True)
    metadata = json.loads(probe.stdout)
    video = next(stream for stream in metadata["streams"] if stream["codec_type"] == "video")
    audio = [stream for stream in metadata["streams"] if stream["codec_type"] == "audio"]
    duration = float(metadata["format"]["duration"])
    assert video["width"] == 1920 and video["height"] == 1080
    assert video["r_frame_rate"] == "30/1"
    assert 10.0 <= duration <= 10.4
    assert audio, "clip-level original VIDEO audio should produce an audio stream"
    hashes = []
    for timestamp in (0.5, 2.4, 4.5, 6.5, 8.5, 9.8):
        frame = subprocess.run([
            "ffmpeg", "-v", "error", "-ss", str(timestamp), "-i", str(OUTPUT),
            "-frames:v", "1", "-f", "md5", "-",
        ], check=True, capture_output=True, text=True)
        hashes.append(frame.stdout.strip())
    assert len(set(hashes)) >= 5
    print(json.dumps({
        "output": str(OUTPUT), "duration_seconds": duration,
        "width": video["width"], "height": video["height"], "fps": video["r_frame_rate"],
        "audio_streams": len(audio), "unique_review_frames": len(set(hashes)),
    }, indent=2))

if __name__ == "__main__":
    main()
