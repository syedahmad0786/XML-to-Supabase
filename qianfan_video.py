#!/usr/bin/env python3
"""
Baidu Qianfan Video Generation Script

Uses the Baidu Qianfan platform (with Vidu model integration) to generate
videos from text prompts or images. New accounts get ~1M free tokens.

Setup:
    1. Register at https://qianfan.cloud.baidu.com
    2. Get your API Key (AK) and Secret Key (SK)
    3. Copy .env.example to .env and fill in credentials
    4. pip install -r requirements.txt

Usage:
    python qianfan_video.py --prompt "A cat playing piano" --output cat.mp4
    python qianfan_video.py --image photo.jpg --output animated.mp4
"""

import argparse
import base64
import json
import os
import sys
import time

import requests

from config import (
    QIANFAN_AK,
    QIANFAN_SK,
    QIANFAN_AUTH_URL,
    QIANFAN_VIDEO_API_BASE,
    VIDU_DEFAULT_DURATION,
    VIDU_DEFAULT_RESOLUTION,
    VIDU_DEFAULT_MODEL,
    DEFAULT_OUTPUT_DIR,
)


def get_access_token(ak: str, sk: str) -> str:
    """Get an OAuth 2.0 access token from Baidu using AK/SK credentials."""
    params = {
        "grant_type": "client_credentials",
        "client_id": ak,
        "client_secret": sk,
    }
    response = requests.post(QIANFAN_AUTH_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    if "access_token" not in data:
        print(f"Error obtaining access token: {data}")
        sys.exit(1)

    print(f"Access token obtained (expires in {data.get('expires_in', '?')}s)")
    return data["access_token"]


def encode_image(image_path: str) -> str:
    """Read and base64-encode an image file."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def submit_video_task(
    access_token: str,
    prompt: str = "",
    image_path: str = "",
    duration: int = VIDU_DEFAULT_DURATION,
    resolution: str = VIDU_DEFAULT_RESOLUTION,
    model: str = VIDU_DEFAULT_MODEL,
) -> str:
    """
    Submit a video generation task to the Qianfan platform.

    Returns the task ID for polling.
    """
    url = f"{QIANFAN_VIDEO_API_BASE}/generation"
    params = {"access_token": access_token}

    payload = {
        "model": model,
        "duration": duration,
        "resolution": resolution,
    }

    if prompt:
        payload["prompt"] = prompt

    if image_path:
        if not os.path.exists(image_path):
            print(f"Error: Image file not found: {image_path}")
            sys.exit(1)
        payload["image"] = encode_image(image_path)
        payload["mode"] = "image_to_video"
    else:
        payload["mode"] = "text_to_video"

    print(f"Submitting {payload['mode']} task...")
    print(f"  Model: {model} | Duration: {duration}s | Resolution: {resolution}")
    if prompt:
        print(f"  Prompt: {prompt}")
    if image_path:
        print(f"  Image: {image_path}")

    response = requests.post(
        url,
        params=params,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()

    if "error_code" in data:
        print(f"API Error {data['error_code']}: {data.get('error_msg', 'Unknown')}")
        sys.exit(1)

    task_id = data.get("task_id", data.get("taskId", ""))
    if not task_id:
        print(f"Unexpected response (no task_id): {json.dumps(data, indent=2)}")
        sys.exit(1)

    print(f"Task submitted! ID: {task_id}")
    return task_id


def poll_task_status(access_token: str, task_id: str, max_wait: int = 600) -> dict:
    """
    Poll the task status until completion or timeout.

    Returns the completed task result dict.
    """
    url = f"{QIANFAN_VIDEO_API_BASE}/query"
    params = {"access_token": access_token}
    payload = {"task_id": task_id}

    start_time = time.time()
    poll_interval = 5  # seconds

    print("Waiting for video generation to complete...")

    while time.time() - start_time < max_wait:
        response = requests.post(
            url,
            params=params,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        status = data.get("status", data.get("taskStatus", "unknown"))
        elapsed = int(time.time() - start_time)

        if status in ("SUCCESS", "success", "completed"):
            print(f"\nVideo generation completed in {elapsed}s!")
            return data

        if status in ("FAILED", "failed", "error"):
            print(f"\nTask failed: {json.dumps(data, indent=2)}")
            sys.exit(1)

        # Still processing
        print(f"  [{elapsed}s] Status: {status}...", end="\r")
        time.sleep(poll_interval)

    print(f"\nTimeout after {max_wait}s. Task may still be processing.")
    print(f"You can check manually with task_id: {task_id}")
    sys.exit(1)


def download_video(result: dict, output_path: str) -> str:
    """Download the generated video from the result URL."""
    video_url = (
        result.get("video_url")
        or result.get("videoUrl")
        or result.get("result", {}).get("video_url", "")
    )

    if not video_url:
        # Try to find it in nested structures
        for key in ("data", "result", "output"):
            nested = result.get(key, {})
            if isinstance(nested, dict):
                video_url = nested.get("video_url") or nested.get("videoUrl", "")
                if video_url:
                    break

    if not video_url:
        print("Warning: Could not find video URL in response.")
        print(f"Full response: {json.dumps(result, indent=2, ensure_ascii=False)}")
        return ""

    # Ensure output directory exists
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    print(f"Downloading video to {output_path}...")
    response = requests.get(video_url, stream=True, timeout=120)
    response.raise_for_status()

    total_size = int(response.headers.get("content-length", 0))
    downloaded = 0

    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            downloaded += len(chunk)
            if total_size:
                pct = (downloaded / total_size) * 100
                print(f"  Downloaded: {pct:.1f}%", end="\r")

    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\nSaved: {output_path} ({file_size_mb:.1f} MB)")
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Generate videos using Baidu Qianfan API (Vidu model)"
    )
    parser.add_argument(
        "--prompt", type=str, default="", help="Text prompt for video generation"
    )
    parser.add_argument(
        "--image", type=str, default="", help="Path to input image for image-to-video"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=os.path.join(DEFAULT_OUTPUT_DIR, "output.mp4"),
        help="Output video file path (default: output/output.mp4)",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=VIDU_DEFAULT_DURATION,
        choices=[5, 10],
        help="Video duration in seconds (default: 5)",
    )
    parser.add_argument(
        "--resolution",
        type=str,
        default=VIDU_DEFAULT_RESOLUTION,
        choices=["720p", "1080p"],
        help="Video resolution (default: 1080p)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=VIDU_DEFAULT_MODEL,
        choices=["turbo", "lite", "pro"],
        help="Model tier (default: turbo — free tier)",
    )
    parser.add_argument(
        "--ak", type=str, default="", help="API Key (overrides .env)"
    )
    parser.add_argument(
        "--sk", type=str, default="", help="Secret Key (overrides .env)"
    )
    args = parser.parse_args()

    if not args.prompt and not args.image:
        parser.error("Provide at least --prompt or --image")

    ak = args.ak or QIANFAN_AK
    sk = args.sk or QIANFAN_SK

    if not ak or not sk:
        print("Error: Missing API credentials.")
        print("Set QIANFAN_AK and QIANFAN_SK in .env or pass --ak and --sk")
        print("Register at: https://qianfan.cloud.baidu.com")
        sys.exit(1)

    # Step 1: Authenticate
    access_token = get_access_token(ak, sk)

    # Step 2: Submit video generation task
    task_id = submit_video_task(
        access_token=access_token,
        prompt=args.prompt,
        image_path=args.image,
        duration=args.duration,
        resolution=args.resolution,
        model=args.model,
    )

    # Step 3: Poll until complete
    result = poll_task_status(access_token, task_id)

    # Step 4: Download the video
    download_video(result, args.output)

    print("\nDone! Your video is ready.")


if __name__ == "__main__":
    main()
