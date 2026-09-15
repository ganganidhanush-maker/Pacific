import os
import sys
import json
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "assets" / "raw_videos"
VIDEOS_DIR = BASE_DIR / "assets" / "videos"
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

# 1280x720 centered crop to 720x720
CROP_FILTER = "crop=720:720:280:0,fps=24,format=yuv420p"

CLIPS = {
    "idle": [
        {"id": "idle_1", "src": "waiting_take2_raw.mp4", "start": 0.0, "duration": 5.0, "style": "calm_attentive"},
        {"id": "idle_2", "src": "waiting_take2_raw.mp4", "start": 5.0, "duration": 5.0, "style": "natural_blink"},
        {"id": "idle_3", "src": "idle_raw.mp4", "start": 0.0, "duration": 5.0, "style": "subtle_tilt"},
        {"id": "idle_4", "src": "idle_raw.mp4", "start": 5.0, "duration": 5.0, "style": "gentle_smile"},
        {"id": "idle_5", "src": "waiting_raw.mp4", "start": 0.0, "duration": 5.0, "style": "focused_listen"},
        {"id": "idle_6", "src": "waiting_raw.mp4", "start": 5.0, "duration": 5.0, "style": "relaxed_posture"},
    ],
    "thinking": [
        {"id": "thinking_1", "src": "thinking_raw.mp4", "start": 0.0, "duration": 5.0, "style": "contemplative_upward"},
        {"id": "thinking_2", "src": "thinking_raw.mp4", "start": 5.0, "duration": 5.0, "style": "calculating_deep"},
        {"id": "thinking_3", "src": "speaking_take3_raw.mp4", "start": 0.0, "duration": 2.1, "style": "attentive_pause"},
    ],
    "speaking": [
        {"id": "speaking_1", "src": "speaking_take3_raw.mp4", "start": 2.1, "duration": 3.4, "tempo": "fast", "style": "energetic_affirmation"},
        {"id": "speaking_2", "src": "speaking_take3_raw.mp4", "start": 5.5, "duration": 3.7, "tempo": "medium", "style": "articulate_statement"},
        {"id": "speaking_3", "src": "speaking_take3_raw.mp4", "start": 10.4, "duration": 4.1, "tempo": "medium", "style": "expressive_explanation"},
        {"id": "speaking_4", "src": "speaking_take3_raw.mp4", "start": 14.5, "duration": 5.3, "tempo": "expressive", "style": "concluding_remark"},
        {"id": "speaking_5", "src": "speaking_raw.mp4", "start": 0.0, "duration": 4.15, "tempo": "fast", "style": "rapid_response"},
        {"id": "speaking_6", "src": "speaking_raw_v2.mp4", "start": 0.0, "duration": 5.0, "tempo": "medium", "style": "conversational_flow"},
        {"id": "speaking_7", "src": "speaking_raw_v2.mp4", "start": 5.0, "duration": 5.0, "tempo": "expressive", "style": "animated_explanation"},
    ]
}

def render_clip(src_path: Path, dst_path: Path, start: float, duration: float):
    print(f"  -> Rendering {dst_path.name} from {src_path.name} ({start}s to {start + duration}s)...")
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-i", str(src_path),
        "-t", str(duration),
        "-vf", CROP_FILTER,
        "-c:v", "libx264",
        "-crf", "19",
        "-preset", "fast",
        "-movflags", "+faststart",
        "-an",
        str(dst_path)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Error rendering {dst_path.name}: {res.stderr[:300]}")
        return False
    return True

def stitch_master(clip_paths, dst_path: Path):
    print(f"  -> Stitching master composite: {dst_path.name} ({len(clip_paths)} clips)...")
    # Concat demuxer
    list_file = dst_path.parent / f"concat_{dst_path.stem}.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for p in clip_paths:
            f.write(f"file '{p.resolve().as_posix()}'\n")
    
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        "-movflags", "+faststart",
        str(dst_path)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if list_file.exists():
        list_file.unlink()
    if res.returncode != 0:
        print(f"Error stitching {dst_path.name}: {res.stderr[:300]}")
        return False
    return True

def main():
    print("==================================================")
    print("   OCTOPUS AI — AVATAR VIDEO PIPELINE BUILDER    ")
    print("==================================================")

    manifest = {"idle": [], "thinking": [], "speaking": []}

    for state, clips in CLIPS.items():
        print(f"\nProcessing {state.upper()} clips ({len(clips)} items)...")
        rendered_paths = []
        for c in clips:
            src = RAW_DIR / c["src"]
            dst = VIDEOS_DIR / f"{c['id']}.mp4"
            if not src.exists():
                print(f"Warning: Source video {src} not found!")
                continue
            
            success = render_clip(src, dst, c["start"], c["duration"])
            if success and dst.exists():
                rendered_paths.append(dst)
                entry = {
                    "id": c["id"],
                    "file": f"/assets/videos/{dst.name}",
                    "duration": c["duration"],
                    "style": c["style"]
                }
                if "tempo" in c:
                    entry["tempo"] = c["tempo"]
                manifest[state].append(entry)

        # Stitch master composite for backwards-compatibility / master reel
        if rendered_paths:
            master_dst = VIDEOS_DIR / f"{state}.mp4"
            stitch_master(rendered_paths, master_dst)

    # Save manifest
    manifest_path = VIDEOS_DIR / "video_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n[OK] Video manifest saved to {manifest_path}")

    # Summary
    print("\nSummary of generated clips:")
    for state, items in manifest.items():
        print(f"  • {state.capitalize()}: {len(items)} clips (total {sum(x['duration'] for x in items):.1f}s)")

if __name__ == "__main__":
    main()
