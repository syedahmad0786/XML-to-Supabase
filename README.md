# Baidu VidPress & Video Generation — Free Access Guide

A comprehensive toolkit for using Baidu's AI video generation services (VidPress, Huixiang/MuseSteamer, Qianfan+Vidu) **for free**.

---

## Table of Contents

- [Overview of Free Methods](#overview-of-free-methods)
- [Method 1: Huixiang Platform (Easiest — Free Beta)](#method-1-huixiang-platform-easiest--free-beta)
- [Method 2: Qianfan API + Vidu (Developer — Free Credits)](#method-2-qianfan-api--vidu-developer--free-credits)
- [Method 3: Baidu Search Built-in Video Generator](#method-3-baidu-search-built-in-video-generator)
- [Setup & Installation](#setup--installation)
- [Usage](#usage)
- [International Access Notes](#international-access-notes)
- [Limitations](#limitations)

---

## Overview of Free Methods

| Method | Type | Free Tier | Language | Access |
|--------|------|-----------|----------|--------|
| **Huixiang (绘想)** | Web platform | Unlimited during beta | Chinese | huixiang.baidu.com |
| **Qianfan API + Vidu** | REST API | ~1M free tokens for new accounts | Chinese/English | qianfan.cloud.baidu.com |
| **Baidu Search Video** | Web-based | Free (integrated into search) | Chinese | baidu.com |

---

## Method 1: Huixiang Platform (Easiest — Free Beta)

**Huixiang (绘想)** is Baidu's consumer-facing AI video creation platform powered by the **MuseSteamer** model. It is currently in **free public beta**.

### What You Get (Free)
- Generate 10-second, 1080p cinematic-quality video clips
- Image-to-video generation from a single uploaded image
- Synchronized Chinese dialogue and sound effects
- Turbo model (fastest) is free during beta

### Step-by-Step Sign Up

1. **Go to** [https://huixiang.baidu.com](https://huixiang.baidu.com)
2. **Click** "Login Now" (登录) in the upper right
3. **Create a Baidu account** if you don't have one:
   - Visit [https://passport.baidu.com](https://passport.baidu.com)
   - Register with a phone number (Chinese phone numbers work best; international numbers may work via the Baidu app)
4. **Log in** and start creating videos immediately
5. **Select the Turbo model** — this is the free version during beta

### Model Tiers Available
- **Turbo** — Free during beta, fastest generation
- **Lite** — Balanced quality/speed
- **Pro** — Highest quality, longest generation time

### Tips for Unlimited Usage
- The Turbo version has no stated generation limits during the beta period
- Queue times may increase during peak hours (evenings CST)
- Download your videos immediately as beta content may not be stored permanently

---

## Method 2: Qianfan API + Vidu (Developer — Free Credits)

The **Qianfan Large Model Platform** is Baidu's developer API platform. It integrates the **Vidu** video generation model and provides **free credits for new accounts**.

### What You Get (Free)
- Free credits equivalent to ~1,000,000 tokens on sign-up
- REST API access for programmatic video generation
- Python/Java/Go SDKs available
- Vidu model: high-dynamics video generation, multi-style transformation, subject reference

### Step-by-Step Setup

1. **Register at** [https://qianfan.cloud.baidu.com](https://qianfan.cloud.baidu.com)
   - Or international portal: [https://intl.cloud.baidu.com](https://intl.cloud.baidu.com)
2. **Complete real-name verification** (required for API access)
3. **Navigate to** Model Services → Video Generation
4. **Apply for Vidu API access** (approval typically within hours)
5. **Get your credentials:**
   - `API Key` (Access Key / AK)
   - `Secret Key` (SK)
6. **Set environment variables:**
   ```bash
   export QIANFAN_AK="your_access_key"
   export QIANFAN_SK="your_secret_key"
   ```
7. **Install the SDK:**
   ```bash
   pip install qianfan
   ```
8. **Run the included script:**
   ```bash
   python qianfan_video.py --prompt "A cat playing piano" --output video.mp4
   ```

### Maximizing Free Credits
- Free credits are granted per new account
- Set spending limits in the console to avoid accidental charges after credits expire
- Use the Lite/Turbo tier for lower token consumption
- Monitor your usage at the Qianfan dashboard

---

## Method 3: Baidu Search Built-in Video Generator

Baidu has integrated **MuseSteamer 2.0** directly into Baidu Search, allowing **free** script-to-video generation.

### How to Use
1. Go to [https://www.baidu.com](https://www.baidu.com)
2. Search for video-creation-related queries
3. Use the integrated video creation tools that appear in search results
4. Generate videos from text scripts directly in the browser

---

## Setup & Installation

### Prerequisites
- Python 3.8+
- A Baidu account (free to create)
- For API method: Qianfan API credentials

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Configure Credentials
```bash
cp .env.example .env
# Edit .env and add your Baidu API credentials
```

---

## Usage

### Using the Qianfan API Script

```bash
# Text-to-video generation
python qianfan_video.py --prompt "A sunset over the ocean with waves" --output sunset.mp4

# Image-to-video generation
python qianfan_video.py --image input.jpg --output animated.mp4

# With custom parameters
python qianfan_video.py --prompt "City timelapse" --duration 10 --resolution 1080p --output city.mp4
```

### Using the Huixiang Automation Script

```bash
# Interactive mode — opens browser and guides you through the process
python huixiang_helper.py --interactive

# Batch processing mode (requires Baidu cookies)
python huixiang_helper.py --batch images/ --output videos/
```

---

## International Access Notes

Baidu's services are primarily designed for users in China. International users should be aware of:

1. **Language**: Most interfaces are in Mandarin Chinese. Use browser translation (Chrome/Edge built-in translate works well).
2. **Account Registration**: A Chinese phone number provides the smoothest experience. The Baidu app sometimes accepts international numbers.
3. **Network Access**: Some Baidu services may be slow or restricted from outside China. Consider:
   - Using the international portal at [intl.cloud.baidu.com](https://intl.cloud.baidu.com)
   - Accessing during Chinese off-peak hours (morning UTC)
4. **API Access**: The Qianfan API is accessible internationally via `intl.cloud.baidu.com`

---

## Limitations

- **VidPress specifically** does not have a public API — it's an internal Baidu tool used on the Haokan platform
- **Huixiang beta** may end and transition to paid tiers (Basic free w/ watermark, Pro at 39 yuan/month, Enterprise custom)
- **Qianfan free credits** are one-time per account and will switch to pay-as-you-go once exhausted
- **Video duration** is currently limited to ~10 seconds per generation on Huixiang
- **Language**: All platforms primarily support Mandarin Chinese content
- **Content policies**: Baidu enforces Chinese content regulations on generated videos

---

## Project Structure

```
├── README.md                # This guide
├── requirements.txt         # Python dependencies
├── .env.example             # Environment variable template
├── qianfan_video.py         # Qianfan API video generation script
├── huixiang_helper.py       # Huixiang platform helper/automation
└── config.py                # Shared configuration
```

---

## Useful Links

- [Huixiang Platform](https://huixiang.baidu.com/) — Free video generation (beta)
- [Qianfan Console](https://qianfan.cloud.baidu.com) — Developer API platform
- [Baidu AI Cloud (International)](https://intl.cloud.baidu.com/en) — International portal
- [Baidu Research — VidPress Blog](https://research.baidu.com/Blog/index-view?id=134) — Original VidPress paper
- [Vidu Studio](https://www.vidu.studio) — Vidu video model (integrated with Qianfan)
- [Baidu Passport](https://passport.baidu.com) — Create a Baidu account
