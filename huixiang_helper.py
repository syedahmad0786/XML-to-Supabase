#!/usr/bin/env python3
"""
Huixiang (绘想) Platform Helper

Helper script for using Baidu's Huixiang free video generation platform.
Huixiang uses the MuseSteamer model and is FREE during the public beta.

This script helps with:
  - Opening the platform with the right URLs
  - Preparing images for upload (resizing, format conversion)
  - Guiding you through the web interface step-by-step

Usage:
    python huixiang_helper.py --interactive
    python huixiang_helper.py --prepare-image photo.jpg
"""

import argparse
import os
import sys
import webbrowser

from config import HUIXIANG_URL

try:
    from PIL import Image
except ImportError:
    Image = None


# Huixiang recommended image specs
RECOMMENDED_WIDTH = 1280
RECOMMENDED_HEIGHT = 720
SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE_MB = 10


def open_huixiang():
    """Open the Huixiang platform in the default browser."""
    print("Opening Huixiang (绘想) platform...")
    print(f"URL: {HUIXIANG_URL}")
    webbrowser.open(HUIXIANG_URL)


def prepare_image(image_path: str, output_dir: str = "output") -> str:
    """
    Prepare an image for upload to Huixiang.

    - Validates format
    - Resizes if too large
    - Converts to JPEG if needed
    - Checks file size
    """
    if Image is None:
        print("Warning: Pillow not installed. Skipping image preparation.")
        print("Install with: pip install Pillow")
        return image_path

    if not os.path.exists(image_path):
        print(f"Error: File not found: {image_path}")
        sys.exit(1)

    ext = os.path.splitext(image_path)[1].lower()
    if ext not in SUPPORTED_FORMATS:
        print(f"Warning: {ext} may not be supported. Supported: {SUPPORTED_FORMATS}")

    img = Image.open(image_path)
    original_size = img.size
    print(f"Original image: {original_size[0]}x{original_size[1]} ({ext})")

    # Resize if larger than recommended
    if img.width > RECOMMENDED_WIDTH * 2 or img.height > RECOMMENDED_HEIGHT * 2:
        img.thumbnail((RECOMMENDED_WIDTH * 2, RECOMMENDED_HEIGHT * 2), Image.LANCZOS)
        print(f"Resized to: {img.width}x{img.height}")

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Save as JPEG for best compatibility
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}_prepared.jpg")

    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    img.save(output_path, "JPEG", quality=90)

    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"Saved prepared image: {output_path} ({file_size_mb:.1f} MB)")

    if file_size_mb > MAX_FILE_SIZE_MB:
        print(f"Warning: File is {file_size_mb:.1f} MB (max recommended: {MAX_FILE_SIZE_MB} MB)")
        print("Consider using a lower quality or smaller image.")

    return output_path


def interactive_guide():
    """Walk the user through using Huixiang step by step."""
    print("=" * 60)
    print("  Huixiang (绘想) — Free AI Video Generation Guide")
    print("  Powered by Baidu MuseSteamer model")
    print("=" * 60)
    print()
    print("Huixiang is currently in FREE public beta.")
    print("The Turbo model is completely free with no stated limits.")
    print()

    print("STEP 1: Open the Platform")
    print("-" * 40)
    print(f"  URL: {HUIXIANG_URL}")
    input("  Press Enter to open in your browser...")
    open_huixiang()
    print()

    print("STEP 2: Log In with Baidu Account")
    print("-" * 40)
    print("  - Click '登录' (Login) in the top-right corner")
    print("  - Use your Baidu account credentials")
    print("  - If you don't have one, register at: https://passport.baidu.com")
    print("  - Tip: Use browser translation if the page is in Chinese")
    input("  Press Enter when logged in...")
    print()

    print("STEP 3: Choose Generation Mode")
    print("-" * 40)
    print("  Options:")
    print("  a) Image-to-Video: Upload a photo to animate it")
    print("  b) Text-to-Video: Describe what you want")
    print()

    mode = input("  Which mode? (a/b): ").strip().lower()
    print()

    if mode == "a":
        print("STEP 4a: Upload Your Image")
        print("-" * 40)
        print("  - Click the upload area on the platform")
        print("  - Select your image (JPG/PNG recommended)")
        print("  - Recommended: 1280x720 or similar 16:9 ratio")
        print()

        prep = input("  Want to prepare/optimize an image first? (y/n): ").strip().lower()
        if prep == "y":
            img_path = input("  Enter image path: ").strip()
            if img_path:
                prepare_image(img_path)
        print()
    else:
        print("STEP 4b: Enter Your Prompt")
        print("-" * 40)
        print("  - Type a description of the video you want")
        print("  - Chinese prompts work best (use Google Translate if needed)")
        print("  - Example: 一只猫在弹钢琴 (A cat playing piano)")
        print()

    print("STEP 5: Select Model & Generate")
    print("-" * 40)
    print("  - Choose 'Turbo' model (FREE during beta)")
    print("  - Click the generate button (生成)")
    print("  - Wait 30-120 seconds for generation")
    print("  - Download the result when ready")
    print()

    print("STEP 6: Download Your Video")
    print("-" * 40)
    print("  - Click the download button on the generated video")
    print("  - Video will be in 1080p MP4 format")
    print("  - You can generate as many videos as you want (free beta)")
    print()

    print("=" * 60)
    print("  Tips for Best Results:")
    print("  - Use clear, specific descriptions")
    print("  - High-quality input images produce better animations")
    print("  - Try different prompts if results aren't satisfactory")
    print("  - Peak hours (evening CST) may have longer queue times")
    print("=" * 60)


def batch_prepare_images(input_dir: str, output_dir: str = "output"):
    """Prepare all images in a directory for Huixiang upload."""
    if not os.path.isdir(input_dir):
        print(f"Error: Directory not found: {input_dir}")
        sys.exit(1)

    images = [
        f
        for f in os.listdir(input_dir)
        if os.path.splitext(f)[1].lower() in SUPPORTED_FORMATS
    ]

    if not images:
        print(f"No supported images found in {input_dir}")
        return

    print(f"Found {len(images)} images to prepare")

    for img_file in images:
        img_path = os.path.join(input_dir, img_file)
        print(f"\nProcessing: {img_file}")
        prepare_image(img_path, output_dir)

    print(f"\nAll images prepared in: {output_dir}/")


def main():
    parser = argparse.ArgumentParser(
        description="Huixiang (绘想) free video generation helper"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Launch interactive step-by-step guide",
    )
    parser.add_argument(
        "--prepare-image",
        type=str,
        default="",
        help="Prepare a single image for upload",
    )
    parser.add_argument(
        "--batch",
        type=str,
        default="",
        help="Prepare all images in a directory",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="output",
        help="Output directory for prepared images (default: output)",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Just open the Huixiang platform in browser",
    )
    args = parser.parse_args()

    if args.open:
        open_huixiang()
    elif args.interactive:
        interactive_guide()
    elif args.prepare_image:
        prepare_image(args.prepare_image, args.output)
    elif args.batch:
        batch_prepare_images(args.batch, args.output)
    else:
        parser.print_help()
        print("\nQuick start: python huixiang_helper.py --interactive")


if __name__ == "__main__":
    main()
