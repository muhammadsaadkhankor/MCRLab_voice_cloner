# 🎙️ MCRLab Voice Cloner

**An advanced AI-powered voice cloning system developed at MCR Lab** for research on realistic, expressive, and adaptive speech synthesis.  
The system allows users to input their own voice samples along with transcriptions to generate personalized speech models — similar in concept to commercial TTS systems, but **built for experimentation, customization, and academic exploration**.

---

## 🚀 Features
- 🎧 **Voice Recording & Uploading:** Capture or upload custom voice samples.
- 🧠 **Automatic Transcription:** Speech-to-text processing for reference alignment.
- 🗣️ **Personalized Speech Generation:** Generate lifelike speech using cloned voices.
- 🧩 **Modular Design:** Separate backend (Python) and frontend (React/Next.js).
- 🧪 **Research-Oriented:** Built for experimentation and AI model testing within MCR Lab.

---

## 🛠️ Installation & Run

```bash
# 1. Create Conda Environment
conda create -n <env-name> python==3.11
conda activate <env-name>
# Tested with Python 3.11; versions >=3.11 are also supported

# 2. Clone the Repository
git clone https://github.com/muhammadsaadkhankor/MCRLab_voice_cloner.git
cd MCRLab_voice_cloner

# 3. Install Backend Dependencies
pip install -r backend_requirements.txt
pip install -r requirements.txt

# 4. Setup Frontend
cd frontend
npm install
cd ..

# 5. Run Backend
python app.py

# 6. Run Frontend
cd frontend
npm start
