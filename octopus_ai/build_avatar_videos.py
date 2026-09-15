import os
import sys
import json
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "assets" / "raw_videos"
VIDEOS_DIR = BASE_DIR / "assets" / "videos"
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

# 1280x720 centered crop to 720x720 with pure studio contrast
CROP_FILTER = "crop=720:720:280:0,fps=24,format=yuv420p"

CLIPS = {
    # IDLE: 100% STRICTLY CLOSED MOUTH AT ALL TIMES (Exclusively from Normal_Waiting_DO____Keep_t)
    "idle": [
        {"id": "idle_1", "src": "waiting_take2_raw.mp4", "start": 0.0, "duration": 10.0, "style": "calm_natural_waiting"},
        {"id": "idle_2", "src": "waiting_take2_raw.mp4", "start": 0.0, "duration": 5.0, "style": "attentive_poise"},
        {"id": "idle_3", "src": "waiting_take2_raw.mp4", "start": 4.5, "duration": 5.5, "style": "natural_blink_breathing"},
        {"id": "idle_4", "src": "waiting_take2_raw.mp4", "start": 1.5, "duration": 5.0, "style": "gentle_awareness"},
        {"id": "idle_5", "src": "waiting_take2_raw.mp4", "start": 3.0, "duration": 5.0, "style": "focused_listening"},
        {"id": "idle_6", "src": "waiting_take2_raw.mp4", "start": 2.0, "duration": 5.5, "style": "relaxed_presence"},
    ],
    # THINKING: Contemplative, 100% closed mouth, attentive pause before reply
    "thinking": [
        {"id": "thinking_1", "src": "speaking_take3_raw.mp4", "start": 0.0, "duration": 2.0, "style": "attentive_listening_pause"},
        {"id": "thinking_2", "src": "waiting_take2_raw.mp4", "start": 0.0, "duration": 4.0, "style": "calm_processing"},
        {"id": "thinking_3", "src": "waiting_take2_raw.mp4", "start": 3.5, "duration": 4.0, "style": "contemplative_ponder"},
    ],
    # SPEAKING: Dynamic mouth movement synchronized with speech audio
    "speaking": [
        {"id": "speaking_1", "src": "speaking_take3_raw.mp4", "start": 2.1, "duration": 3.4, "tempo": "fast", "style": "energetic_affirmation"},
        {"id": "speaking_2", "src": "speaking_take3_raw.mp4", "start": 5.5, "duration": 3.7, "tempo": "medium", "style": "articulate_statement"},
        {"id": "speaking_3", "src": "speaking_take3_raw.mp4", "start": 10.4, "duration": 4.1, "tempo": "medium", "style": "expressive_explanation"},
        {"id": "speaking_4", "src": "speaking_take3_raw.mp4", "start": 14.5, "duration": 5.3, "tempo": "expressive", "style": "concluding_remark"},
        {"id": "speaking_5", "src": "speaking_raw.mp4", "start": 0.0, "duration": 4.15, "tempo": "fast", "style": "rapid_response"},
        {"id": "speaking_6", "src": "speaking_raw_v2.mp4", "start": 0.0, "duration": 5.0, "tempo": "medium", "style": "conversational_flow"},
        {"id": "speaking_7", "src": "speaking_raw_v2.mp4", "start": 5.0, "duration": 5.0, "tempo": "expressive", "style": "animated_explanation"},
        {"id": "speaking_8", "src": "idle_raw.mp4", "start": 0.0, "duration": 5.0, "tempo": "medium", "style": "smiling_dialogue"},
        {"id": "speaking_9", "src": "idle_raw.mp4", "start": 5.0, "duration": 5.0, "tempo": "expressive", "style": "animated_response"},
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
        "-crf", "18",
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

def render_pingpong_idle(src_path: Path, dst_path: Path):
    """Generate a seamless 19-second forward-and-reverse continuous loop from Normal_Waiting with zero jumps."""
    print(f"  -> Rendering seamless continuous ping-pong master {dst_path.name}...")
    # Cut first 9.5s forward, then reverse 9.5s, avoiding any jump cut at endpoints
    filter_complex = (
        f"[0:v]{CROP_FILTER},trim=0:9.5,setpts=PTS-STARTPTS[fwd];"
        f"[0:v]{CROP_FILTER},trim=0.5:9.5,reverse,setpts=PTS-STARTPTS[rev];"
        f"[fwd][rev]concat=n=2:v=1:a=0[outv]"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", str(src_path),
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "fast",
        "-movflags", "+faststart",
        "-an",
        str(dst_path)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Error rendering ping-pong idle: {res.stderr[:300]}")
        return False
    return True

def stitch_master(clip_paths, dst_path: Path):
    print(f"  -> Stitching master composite: {dst_path.name} ({len(clip_paths)} clips)...")
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
    print("   OCTOPUS AI — PURE CLOSED-MOUTH AVATAR PIPELINE  ")
    print("==================================================")

    manifest = {"idle": [], "thinking": [], "speaking": []}

    # 1. Render all clips
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

        # Stitch master composite
        if rendered_paths and state != "idle":
            master_dst = VIDEOS_DIR / f"{state}.mp4"
            stitch_master(rendered_paths, master_dst)

    # 2. Render seamless 19-second ping-pong idle master from Normal_Waiting_DO____Keep_t
    waiting_src = RAW_DIR / "waiting_take2_raw.mp4"
    idle_master = VIDEOS_DIR / "idle.mp4"
    if waiting_src.exists():
        render_pingpong_idle(waiting_src, idle_master)


    # 4. Save manifest
    manifest_path = VIDEOS_DIR / "video_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n[OK] Video manifest saved to {manifest_path}")

    # Summary
    print("\nSummary of sanitized clips:")
    for state, items in manifest.items():
        print(f"  • {state.capitalize()}: {len(items)} clips (total {sum(x['duration'] for x in items):.1f}s)")

if __name__ == "__main__":
    main()
