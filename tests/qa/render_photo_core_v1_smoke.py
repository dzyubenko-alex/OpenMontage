"""Render and verify the autonomous PHOTO_CORE_V1 smoke fixture."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from tools.video.video_compose import VideoCompose


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "photo_core_v1_smoke"
OUTPUT_PATH = REPO_ROOT / "output" / "photo-core-v1-smoke.mp4"


def main() -> None:
    props = json.loads((FIXTURE_DIR / "props.json").read_text(encoding="utf-8"))
    assert props["profiles"]["voice"]["enabled"] is False
    assert props["profiles"]["music"]["enabled"] is False
    assert props["profiles"]["branding"]["enabled"] is False
    assert props["audio"] == {}
    result = VideoCompose().execute(
        {
            "operation": "remotion_render",
            "composition_data": props,
            "public_dir": str(FIXTURE_DIR),
            "output_path": str(OUTPUT_PATH),
            "remotion_timeout_ms": 120_000,
            "browser_executable": "/usr/bin/google-chrome-stable",
        }
    )
    if not result.success:
        raise RuntimeError(result.error)

    probe = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "stream=codec_type,width,height,r_frame_rate:format=duration",
            "-of", "json",
            str(OUTPUT_PATH),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    metadata = json.loads(probe.stdout)
    video = next(stream for stream in metadata["streams"] if stream["codec_type"] == "video")
    audio_streams = [stream for stream in metadata["streams"] if stream["codec_type"] == "audio"]
    duration = float(metadata["format"]["duration"])

    assert video["width"] == 1080
    assert video["height"] == 1080
    assert video["r_frame_rate"] == "30/1"
    assert 10.4 <= duration <= 10.6

    max_volume_db = None
    if audio_streams:
        volume_probe = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-i", str(OUTPUT_PATH),
                "-af", "volumedetect", "-f", "null", "-",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        match = re.search(r"max_volume:\s+(-?[0-9.]+) dB", volume_probe.stderr)
        assert match is not None
        max_volume_db = float(match.group(1))
        assert max_volume_db <= -90

    sample_times = (0.5, 2.5, 3.4, 3.6, 5.0, 7.1, 9.0)
    frame_hashes = []
    for timestamp in sample_times:
        frame = subprocess.run(
            [
                "ffmpeg", "-v", "error", "-ss", str(timestamp),
                "-i", str(OUTPUT_PATH), "-frames:v", "1", "-f", "md5", "-",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        frame_hashes.append(frame.stdout.strip())
    assert len(set(frame_hashes)) == len(frame_hashes)

    print(json.dumps({
        "output": str(OUTPUT_PATH),
        "duration_seconds": duration,
        "width": video["width"],
        "height": video["height"],
        "fps": video["r_frame_rate"],
        "audio_streams": len(audio_streams),
        "max_volume_db": max_volume_db,
        "unique_review_frames": len(set(frame_hashes)),
        "render_seconds": result.duration_seconds,
    }, indent=2))


if __name__ == "__main__":
    main()
