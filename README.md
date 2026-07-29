# NovaCut - Render Deployment

This directory contains the production-ready code optimized specifically for deployment on **Render's Free Tier (512MB RAM)**. 

The architecture has been cleanly separated into a Frontend and Backend, both configured to deploy simultaneously using the provided `render.yaml` Blueprint.

## 🚀 One-Click Deployment Guide

1. **Upload to GitHub**: Push this entire `render-deploy` folder to a new GitHub repository as the root folder.
2. **Sign in to Render**: Go to [Render.com](https://render.com) and log in.
3. **New Blueprint**: Click "New" -> "Blueprint" in the Render dashboard.
4. **Connect Repository**: Connect your newly created GitHub repository.
5. **Apply Blueprint**: Render will automatically read the `render.yaml` file in the root directory and create two services:
   - **`novacut-frontend`**: A Free Static Site (Vite React App).
   - **`novacut-backend`**: A Free Web Service (FastAPI Docker).
6. **Set Environment Variables**: In your Render Dashboard, under the `novacut-backend` service settings, add the required environment variables (e.g., `GEMINI_API_KEY`). See `.env.example`.

## 🛠 Optimizations Applied

- **Memory Optimization (<512 MB RAM)**: PyTorch and `openai-whisper` have been removed from the dependency tree. The application gracefully falls back to using `SpeechRecognition` or `Gemini` API for all AI transcriptions. This guarantees that your instance will not hit Out-Of-Memory (OOM) errors during startup or processing on the Free instance.
- **FFmpeg Linux Support**: The application was reconfigured to automatically locate and utilize the native Linux FFmpeg binaries installed via the Docker container. The heavy Windows `ffmpeg_bin/` `.exe` files have been omitted to save over 300MB of repository bloat.
- **Dynamic CORS & Routing**: The `render.yaml` dynamically configures the frontend to point to the Render-assigned backend URL during the build phase (`VITE_API_BASE_URL`). No manual URL syncing is required. CORS has been configured to cleanly accept traffic without blocking the frontend.

## ⚠️ Free Tier Limitations (Important)

The Render Free Web Service utilizes an ephemeral filesystem. This means that if the server spins down due to inactivity or redeploys, any files saved in `uploads/` or `outputs/`, as well as the SQLite database (`app.db`), will be reset to their initial state. 

For a fully persistent production setup in the future, you would need to connect a managed PostgreSQL database and an AWS S3 bucket for file storage. However, the exact UI, UX, and code functionality from your development environment remains 100% identical.
