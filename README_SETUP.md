# MCR Lab Voice Cloner - Setup Guide

## Prerequisites
- Python 3.11+
- Node.js 18+
- Conda/Miniconda
- Git

## Quick Start

### 1. Clone Repository
```bash
git clone <your-repo-url>
cd neutts-air
```

### 2. Create Conda Environment
```bash
conda create -n gen_voice python=3.11
conda activate gen_voice
```

### 3. Install System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt install espeak ffmpeg
```

**macOS:**
```bash
brew install espeak ffmpeg
```

### 4. Install Python Dependencies
```bash
pip install -r requirements.txt
pip install -r backend_requirements.txt
```

### 5. Install Frontend Dependencies
```bash
cd frontend
npm install
cd ..
```

## Running the Application

### Option 1: Manual Start
**Terminal 1 - Backend:**
```bash
conda activate gen_voice
python app.py
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm start
```

### Option 2: Docker (Alternative)
```bash
./docker-run.sh
```

## Access Application
- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:5000

## Features
1. **Record Voice** - Direct browser recording
2. **Upload Audio** - MP3/WAV file upload
3. **Generate Speech** - Text-to-speech with voice cloning
4. **Create API** - Generate API keys for programmatic access

## API Usage
```bash
curl -X POST http://localhost:5000/api/tts \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"voice_id": "YOUR_VOICE_ID", "text": "Hello world"}'
```

## Troubleshooting
- Ensure conda environment is activated
- Check all dependencies are installed
- Verify ports 3000 and 5000 are available