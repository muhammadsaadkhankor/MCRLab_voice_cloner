from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import soundfile as sf
import whisper
from neuttsair.neutts import NeuTTSAir
import uuid
from datetime import datetime
from pydub import AudioSegment
import json
import hashlib
import numpy as np
import random
import string
from database import VoiceDatabase

app = Flask(__name__)
CORS(app)

# Initialize database
db = VoiceDatabase()

# Initialize Whisper for transcription
whisper_model = whisper.load_model("base")

# Initialize TTS (will be loaded when needed)
tts = None

# Store voice data (in production, use a database)
voice_store = {}
api_keys = {}

def get_tts():
    global tts
    if tts is None:
        tts = NeuTTSAir(
            backbone_repo="neuphonic/neutts-air-q4-gguf",
            backbone_device="cuda",
            codec_repo="neuphonic/neucodec",
            codec_device="cuda"
        )
    return tts

@app.route('/upload_reference', methods=['POST'])
def upload_reference():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file'}), 400
    
    audio_file = request.files['audio']
    voice_name = request.form.get('voice_name', f'Custom Voice {datetime.now().strftime("%H:%M:%S")}')
    
    # Save audio file with unique name
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    temp_path = f"temp_reference_{timestamp}{os.path.splitext(audio_file.filename)[1]}"
    audio_path = f"uploads/voice_{timestamp}.wav"
    text_path = f"uploads/voice_{timestamp}.txt"
    
    os.makedirs('uploads', exist_ok=True)
    audio_file.save(temp_path)
    
    try:
        if temp_path.lower().endswith('.wav'):
            if os.path.exists(audio_path):
                os.remove(audio_path)
            os.rename(temp_path, audio_path)
        else:
            audio = AudioSegment.from_file(temp_path)
            audio = audio.set_channels(1)
            audio = audio.set_frame_rate(24000)
            audio.export(audio_path, format="wav")
            os.remove(temp_path)
        
        result = whisper_model.transcribe(audio_path)
        transcript = result["text"].strip()
        
        with open(text_path, 'w') as f:
            f.write(transcript)
        
        voice_id = db.add_voice(voice_name, audio_path, text_path, is_predefined=False)
        
        return jsonify({
            'audio_path': audio_path,
            'text_path': text_path,
            'transcript': transcript,
            'voice_id': voice_id,
            'voice_name': voice_name
        })
    
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({'error': f'Audio processing failed: {str(e)}'}), 500

def chunk_text_by_duration(text, target_duration_seconds=15):
    """Split text into chunks targeting specific duration (default 15 seconds)
    
    This function estimates speech duration and creates chunks that will generate
    approximately the target duration when converted to speech. It tries to
    respect sentence boundaries when possible for more natural speech.
    """
    import re
    
    # Estimate speaking rate: ~2.2 words per second (conservative for TTS)
    estimated_words_per_second = 2.2
    target_words_per_chunk = int(target_duration_seconds * estimated_words_per_second)
    
    # Split into sentences first
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    chunks = []
    current_chunk = ""
    current_word_count = 0
    
    for sentence in sentences:
        sentence_words = len(sentence.split())
        
        # If adding this sentence would exceed target, start new chunk
        if current_word_count + sentence_words > target_words_per_chunk and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = sentence
            current_word_count = sentence_words
        else:
            # Add sentence to current chunk
            if current_chunk:
                current_chunk += ". " + sentence
            else:
                current_chunk = sentence
            current_word_count += sentence_words
    
    # Add remaining chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    # If no sentence boundaries found or chunks are too large, fall back to word-based splitting
    if not chunks or any(len(chunk.split()) > target_words_per_chunk * 1.5 for chunk in chunks):
        words = text.split()
        chunks = []
        for i in range(0, len(words), target_words_per_chunk):
            chunk = ' '.join(words[i:i + target_words_per_chunk])
            chunks.append(chunk)
    
    return chunks

@app.route('/generate_speech', methods=['POST'])
def generate_speech():
    data = request.json
    input_text = data.get('input_text')
    ref_audio_path = data.get('ref_audio_path')
    ref_text_path = data.get('ref_text_path')
    
    if not all([input_text, ref_audio_path, ref_text_path]):
        return jsonify({'error': 'Missing required parameters'}), 400
    
    try:
        # Read reference text
        with open(ref_text_path, 'r') as f:
            ref_text = f.read().strip()
        
        # Get TTS instance
        tts_instance = get_tts()
        
        # Encode reference once
        ref_codes = tts_instance.encode_reference(ref_audio_path)
        
        # Check if text needs chunking (split for 15-second segments)
        word_count = len(input_text.split())
        estimated_duration = word_count / 2.2  # Conservative estimate
        
        if estimated_duration > 15:  # If estimated duration > 15 seconds
            chunks = chunk_text_by_duration(input_text, target_duration_seconds=15)
            print(f"Word count: {word_count}, Estimated duration: {estimated_duration:.1f}s, Split into {len(chunks)} chunks")
            audio_segments = []
            
            for i, chunk in enumerate(chunks):
                print(f"Processing chunk {i+1}: {chunk[:50]}...")
                wav_chunk = tts_instance.infer(chunk, ref_codes, ref_text)
                print(f"Chunk {i+1} audio length: {len(wav_chunk)/24000:.2f} seconds")
                audio_segments.append(wav_chunk)
                
                import gc
                gc.collect()
                
                if i < len(chunks) - 1:
                    silence = np.zeros(int(0.3 * 24000))
                    audio_segments.append(silence)
            
            wav = np.concatenate(audio_segments)
            print(f"Final audio length: {len(wav)/24000:.2f} seconds")
        else:
            wav = tts_instance.infer(input_text, ref_codes, ref_text)
            print(f"Generated audio length: {len(wav)/24000:.2f} seconds")
        
        # Save as WAV first, then convert to MP3
        wav_path = "temp_output.wav"
        output_path = "output.mp3"
        
        print(f"Saving audio file: {len(wav)} samples, {len(wav)/24000:.2f} seconds")
        sf.write(wav_path, wav, 24000)
        
        # Convert to MP3
        audio = AudioSegment.from_wav(wav_path)
        audio.export(output_path, format="mp3", bitrate="192k")
        
        # Clean up temp WAV file
        os.remove(wav_path)
        
        # Verify the saved file
        file_size = os.path.getsize(output_path)
        print(f"Saved MP3 file size: {file_size} bytes")
        print("Generation completed successfully!")
        
        response = jsonify({'output_path': output_path})
        response.headers['Cache-Control'] = 'no-cache'
        return response
    
    except Exception as e:
        import traceback
        print(f"Error in generate_speech: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    return send_file(filename, as_attachment=True)

def generate_unique_voice_id():
    """Generate a unique voice ID with letters and numbers"""
    while True:
        # Generate 12-character alphanumeric ID (letters + numbers, including capitals)
        voice_id = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        if voice_id not in voice_store:
            return voice_id

@app.route('/create_voice_api', methods=['POST'])
def create_voice_api():
    data = request.json
    voice_name = data.get('voice_name')  # For predefined voices
    audio_path = data.get('audio_path')  # For custom voices
    text_path = data.get('text_path')    # For custom voices
    api_key_name = data.get('api_key_name', 'default')  # Custom API key name
    
    try:
        if voice_name:
            # Handle predefined voice
            voice = db.get_voice_by_name(voice_name)
            if not voice:
                return jsonify({'error': 'Voice not found'}), 404
            
            voice_id = voice['voice_id']
            audio_path = voice['audio_path']
            text_path = voice['text_path']
        elif audio_path and text_path:
            # Handle custom voice
            voice_id = generate_unique_voice_id()
        else:
            return jsonify({'error': 'Missing voice_name or audio/text paths'}), 400
        
        # Generate API key with sk_ prefix
        random_suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        api_key = f"sk_{random_suffix}"
        
        # Store voice data
        voice_store[voice_id] = {
            'audio_path': audio_path,
            'text_path': text_path,
            'api_key_name': api_key_name,
            'created_at': datetime.now().isoformat()
        }
        
        api_keys[api_key] = voice_id
        
        return jsonify({
            'voice_id': voice_id,
            'api_key': api_key,
            'api_key_name': api_key_name,
            'voice_name': voice_name if voice_name else 'Custom Voice'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api')
def api_management():
    with open('api_simple.html', 'r') as f:
        return f.read()

@app.route('/api_old')
def api_management_old():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>API Management - HUMAIN Voice Cloning</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%); min-height: 100vh; }
            .header { background: white; border-bottom: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
            .header-content { max-width: 1200px; margin: 0 auto; padding: 1.5rem 2rem; display: flex; justify-content: space-between; align-items: center; }
            .header-title h1 { font-size: 2rem; font-weight: 800; color: #0f172a; }
            .subtitle { font-size: 0.95rem; color: #64748b; font-weight: 500; }
            .back-btn { padding: 0.75rem 1.5rem; background: #334155; color: white; text-decoration: none; border-radius: 2rem; font-weight: 600; transition: all 0.2s; }
            .back-btn:hover { background: #1e293b; transform: translateY(-1px); }
            .container { max-width: 1200px; margin: 0 auto; padding: 2rem; }
            .section { background: white; border-radius: 1rem; padding: 2rem; margin-bottom: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; }
            .section h2 { font-size: 1.5rem; font-weight: 800; color: #0f172a; margin-bottom: 1rem; }
            .api-creation { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem; margin-bottom: 2rem; }
            .option-card { background: #f8fafc; border: 2px solid #e2e8f0; border-radius: 0.75rem; padding: 1.5rem; text-align: center; transition: all 0.2s; cursor: pointer; }
            .option-card:hover { border-color: #10b981; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(16,185,129,0.15); }
            .option-card h3 { font-size: 1.125rem; font-weight: 700; color: #0f172a; margin-bottom: 0.5rem; }
            .option-card p { color: #64748b; font-size: 0.875rem; margin-bottom: 1rem; }
            .create-btn { width: 100%; padding: 0.875rem 1.5rem; background: #10b981; color: white; border: none; border-radius: 2rem; font-weight: 600; cursor: pointer; transition: all 0.2s; }
            .create-btn:hover { background: #059669; transform: translateY(-1px); }
            .create-btn:disabled { opacity: 0.5; cursor: not-allowed; }
            .voice-selector { margin-bottom: 1rem; }
            .voice-selector select { width: 100%; padding: 0.75rem; border: 1px solid #cbd5e1; border-radius: 0.5rem; font-size: 1rem; }
            .upload-area { border: 2px dashed #cbd5e1; border-radius: 0.75rem; padding: 2rem; text-align: center; margin-bottom: 1rem; transition: all 0.2s; }
            .upload-area:hover { border-color: #10b981; background: #f0fdf4; }
            .upload-btn { padding: 0.75rem 1.5rem; background: #334155; color: white; border: none; border-radius: 0.5rem; cursor: pointer; margin: 0.5rem; }
            .upload-btn:hover { background: #1e293b; }
            .api-credentials { background: #d1fae5; border-radius: 0.75rem; padding: 1.5rem; margin-top: 1rem; display: none; }
            .field { margin: 1rem 0; }
            .field label { display: block; font-weight: 600; margin-bottom: 0.5rem; color: #0f172a; }
            .input-group { display: flex; gap: 0.5rem; }
            .field input { flex: 1; padding: 0.75rem; background: white; border: 1px solid #cbd5e1; border-radius: 0.5rem; font-family: monospace; font-size: 0.875rem; }
            .copy-btn { padding: 0.75rem 1rem; background: #334155; color: white; border: none; border-radius: 0.5rem; cursor: pointer; }
            .copy-btn:hover { background: #1e293b; }
            .usage-docs { background: #0f172a; border-radius: 0.75rem; padding: 1.5rem; margin-top: 1rem; }
            .usage-docs h3 { color: white; margin-bottom: 1rem; }
            .usage-section { margin-bottom: 1.5rem; }
            .usage-section h4 { color: #10b981; margin-bottom: 0.5rem; font-size: 0.95rem; }
            .usage-docs pre { color: #10b981; font-size: 0.875rem; background: #1e293b; padding: 1rem; border-radius: 0.5rem; overflow-x: auto; }
            .loading { display: none; text-align: center; color: #10b981; font-weight: 600; }
            .spinner { display: inline-block; width: 1rem; height: 1rem; border: 2px solid #d1fae5; border-top-color: #10b981; border-radius: 50%; animation: spin 0.8s linear infinite; margin-right: 0.5rem; }
            @keyframes spin { to { transform: rotate(360deg); } }
        </style>
    </head>
    <body>
        <div class="header">
            <div class="header-content">
                <div class="header-title">
                    <h1>🔑 API Management</h1>
                    <p class="subtitle">Create and manage voice cloning APIs</p>
                </div>
                <a href="http://localhost:3000" class="back-btn">← Back to Home</a>
            </div>
        </div>
        
        <div class="container">
            <div class="section">
                <h2>Create New API</h2>
                <div style="text-align: center; margin-bottom: 2rem; padding: 2rem; background: #f0fdf4; border-radius: 0.75rem; border: 2px solid #10b981;">
                    <h3 style="color: #0f172a; margin-bottom: 1rem;">🚀 Create API Instantly</h3>
                    <p style="color: #64748b; margin-bottom: 1.5rem;">Get your API credentials immediately - no voice upload required!</p>
                    
                    <div style="margin-bottom: 1.5rem;">
                        <label style="display: block; font-weight: 600; margin-bottom: 0.5rem; color: #0f172a;">API Name:</label>
                        <input type="text" id="apiNameInput" placeholder="Enter your API name..." style="width: 100%; max-width: 300px; padding: 0.75rem; border: 1px solid #cbd5e1; border-radius: 0.5rem; font-size: 1rem;">
                    </div>
                    
                    <button class="create-btn" onclick="createInstantAPI()" style="width: auto; padding: 1rem 2rem; font-size: 1.1rem;">Create API Now</button>
                </div>
                
                <div style="text-align: center; margin-bottom: 1.5rem;">
                    <span style="color: #64748b; font-size: 0.875rem;">OR upload/record your own voice for custom API</span>
                </div>
                
                <!-- Custom Voice Upload -->
                <div id="customSection">
                    <h3>Upload or Record Custom Voice</h3>
                    
                    <!-- Recording Section -->
                    <div style="margin-bottom: 1.5rem;">
                        <h4 style="margin-bottom: 0.5rem; color: #0f172a;">🎤 Record Your Voice</h4>
                        <div style="display: flex; gap: 1rem; align-items: center; margin-bottom: 1rem;">
                            <button class="create-btn" id="recordBtn" onclick="toggleRecording()" style="width: auto; padding: 0.75rem 1.5rem;">Start Recording</button>
                            <span id="recordingStatus" style="color: #64748b; font-size: 0.875rem;">Click to start recording</span>
                        </div>
                    </div>
                    
                    <!-- Upload Section -->
                    <div style="margin-bottom: 1.5rem;">
                        <h4 style="margin-bottom: 0.5rem; color: #0f172a;">📤 Or Upload Audio File</h4>
                        <div class="upload-area" onclick="document.getElementById('audioFile').click()">
                            <p>📤 Click to upload audio file (WAV/MP3)</p>
                            <p style="font-size: 0.875rem; color: #64748b; margin-top: 0.5rem;">Recommended: 3-15 seconds of clear speech</p>
                            <input type="file" id="audioFile" accept=".wav,.mp3" style="display: none;" onchange="handleFileUpload(event)">
                        </div>
                    </div>
                    
                    <div id="uploadStatus"></div>
                    <div id="transcriptDisplay" style="display: none; background: #d1fae5; padding: 1rem; border-radius: 0.5rem; margin: 1rem 0;">
                        <h4 style="color: #0f172a; margin-bottom: 0.5rem;">📝 Transcript:</h4>
                        <p id="transcriptText" style="color: #334155; margin: 0;"></p>
                    </div>
                    <button class="create-btn" id="createCustomBtn" onclick="createCustomAPI()" disabled>Create API for Custom Voice</button>
                </div>
                
                <div class="loading" id="loading">
                    <span class="spinner"></span>Creating API...
                </div>
                
                <!-- API Credentials Display -->
                <div class="api-credentials" id="apiCredentials">
                    <h3>🎉 API Created Successfully!</h3>
                    <div class="field">
                        <label>API Key Name:</label>
                        <span id="apiKeyName"></span>
                    </div>
                    <div class="field">
                        <label>Voice ID:</label>
                        <div class="input-group">
                            <input type="text" id="voiceId" readonly>
                            <button class="copy-btn" onclick="copyToClipboard('voiceId')">📋</button>
                        </div>
                    </div>
                    <div class="field">
                        <label>API Key (sk_...):</label>
                        <div class="input-group">
                            <input type="text" id="apiKey" readonly>
                            <button class="copy-btn" onclick="copyToClipboard('apiKey')">📋</button>
                        </div>
                    </div>
                    
                    <div class="usage-docs">
                        <h3>📖 How to Use Your API</h3>
                        
                        <div class="usage-section">
                            <h4>Basic Usage:</h4>
                            <pre id="basicUsage"></pre>
                        </div>
                        
                        <div class="usage-section">
                            <h4>With Custom Output Directory:</h4>
                            <pre id="customDirUsage"></pre>
                        </div>
                        
                        <div class="usage-section">
                            <h4>Response Format:</h4>
                            <pre id="responseFormat"></pre>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            let voices = [];
            let uploadedVoice = null;
            let mediaRecorder = null;
            let audioChunks = [];
            let isRecording = false;
            
            window.onload = function() {
                loadVoices();
            };
            
            async function loadVoices() {
                try {
                    const response = await fetch('http://localhost:5000/get_voices');
                    const data = await response.json();
                    voices = data.voices.filter(v => v.audio_exists);
                    
                    const select = document.getElementById('voiceSelect');
                    select.innerHTML = '<option value="">Select a voice...</option>';
                    voices.forEach(voice => {
                        select.innerHTML += `<option value="${voice.name}">${voice.name}</option>`;
                    });
                } catch (error) {
                    console.error('Error loading voices:', error);
                }
            }
            

            
            async function toggleRecording() {
                if (!isRecording) {
                    try {
                        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                        mediaRecorder = new MediaRecorder(stream);
                        audioChunks = [];
                        
                        mediaRecorder.ondataavailable = (event) => {
                            audioChunks.push(event.data);
                        };
                        
                        mediaRecorder.onstop = async () => {
                            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                            await uploadAudio(audioBlob, 'recorded_voice.wav');
                        };
                        
                        mediaRecorder.start();
                        isRecording = true;
                        document.getElementById('recordBtn').textContent = 'Stop Recording';
                        document.getElementById('recordBtn').style.background = '#ef4444';
                        document.getElementById('recordingStatus').textContent = '🔴 Recording... Click to stop';
                        document.getElementById('recordingStatus').style.color = '#ef4444';
                    } catch (error) {
                        alert('Error accessing microphone: ' + error.message);
                    }
                } else {
                    mediaRecorder.stop();
                    mediaRecorder.stream.getTracks().forEach(track => track.stop());
                    isRecording = false;
                    document.getElementById('recordBtn').textContent = 'Start Recording';
                    document.getElementById('recordBtn').style.background = '#10b981';
                    document.getElementById('recordingStatus').textContent = '🎵 Processing recording...';
                    document.getElementById('recordingStatus').style.color = '#10b981';
                }
            }
            
            async function handleFileUpload(event) {
                const file = event.target.files[0];
                if (!file) return;
                
                await uploadAudio(file, file.name);
            }
            
            async function uploadAudio(audioBlob, filename) {
                const formData = new FormData();
                formData.append('audio', audioBlob, filename);
                
                document.getElementById('uploadStatus').innerHTML = '<p style="color: #10b981;">🎵 Processing audio...</p>';
                
                try {
                    const response = await fetch('http://localhost:5000/upload_reference', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const data = await response.json();
                    if (response.ok) {
                        uploadedVoice = data;
                        document.getElementById('uploadStatus').innerHTML = '<p style="color: #10b981;">✅ Audio processed successfully!</p>';
                        
                        // Show transcript
                        document.getElementById('transcriptText').textContent = data.transcript;
                        document.getElementById('transcriptDisplay').style.display = 'block';
                        
                        document.getElementById('createCustomBtn').disabled = false;
                        document.getElementById('recordingStatus').textContent = '✅ Ready to create API';
                        document.getElementById('recordingStatus').style.color = '#10b981';
                    } else {
                        throw new Error(data.error);
                    }
                } catch (error) {
                    document.getElementById('uploadStatus').innerHTML = `<p style="color: #ef4444;">❌ Error: ${error.message}</p>`;
                    document.getElementById('recordingStatus').textContent = 'Click to start recording';
                    document.getElementById('recordingStatus').style.color = '#64748b';
                }
            }
            

            
            async function createInstantAPI() {
                const apiKeyName = document.getElementById('apiNameInput').value.trim();
                if (!apiKeyName) {
                    alert('Please enter an API name');
                    return;
                }
                
                // Generate instant API without voice upload
                const apiKey = 'sk_' + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 23);
                const voiceId = Math.random().toString(36).substring(2, 15);
                
                displayAPICredentials({
                    voice_id: voiceId,
                    api_key: apiKey,
                    api_key_name: apiKeyName
                }, apiKeyName);
            }
            
            async function createCustomAPI() {
                if (!uploadedVoice) {
                    alert('Please upload or record a voice file first');
                    return;
                }
                
                const apiKeyName = document.getElementById('apiNameInput').value.trim();
                if (!apiKeyName) {
                    alert('Please enter an API name');
                    return;
                }
                
                await createAPI({
                    audio_path: uploadedVoice.audio_path,
                    text_path: uploadedVoice.text_path,
                    api_key_name: apiKeyName
                }, apiKeyName);
            }
            
            async function createAPI(requestData, voiceName) {
                document.getElementById('loading').style.display = 'block';
                
                try {
                    const response = await fetch('http://localhost:5000/create_voice_api', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(requestData)
                    });
                    
                    const data = await response.json();
                    if (response.ok) {
                        displayAPICredentials(data, voiceName);
                    } else {
                        throw new Error(data.error);
                    }
                } catch (error) {
                    alert('Error creating API: ' + error.message);
                } finally {
                    document.getElementById('loading').style.display = 'none';
                }
            }
            
            function displayAPICredentials(data, voiceName) {
                document.getElementById('apiKeyName').textContent = data.api_key_name;
                document.getElementById('voiceId').value = data.voice_id;
                document.getElementById('apiKey').value = data.api_key;
                
                document.getElementById('basicUsage').textContent = `curl -X POST http://localhost:5000/api/tts \\
  -H "Authorization: Bearer ${data.api_key}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "voice_id": "${data.voice_id}",
    "text": "Your text here"
  }'`;
                
                document.getElementById('customDirUsage').textContent = `curl -X POST http://localhost:5000/api/tts \\
  -H "Authorization: Bearer ${data.api_key}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "voice_id": "${data.voice_id}",
    "text": "Your text here",
    "output_dir": "my_audio_files"
  }'`;
                
                document.getElementById('responseFormat').textContent = `{
  "success": true,
  "audio_path": "api_outputs/tts_output_20241108_143022.wav",
  "audio_url": "http://localhost:5000/download/api_outputs/tts_output_20241108_143022.wav",
  "voice_id": "${data.voice_id}",
  "output_directory": "api_outputs"
}`;
                
                document.getElementById('apiCredentials').style.display = 'block';
            }
            
            function copyToClipboard(elementId) {
                const element = document.getElementById(elementId);
                element.select();
                document.execCommand('copy');
                alert('Copied to clipboard!');
            }
        </script>
    </body>
    </html>
    '''

@app.route('/api_page')
def api_page():
    voice_id = request.args.get('voice_id')
    api_key = request.args.get('api_key')
    voice_name = request.args.get('voice_name', 'Voice')
    
    if not voice_id or not api_key:
        return "Invalid API credentials", 400
    
    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>API Credentials - {voice_name}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
            .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            h1 {{ color: #333; }}
            .field {{ margin: 20px 0; }}
            label {{ display: block; font-weight: bold; margin-bottom: 5px; }}
            input {{ width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; font-family: monospace; }}
            .copy-btn {{ margin-left: 10px; padding: 8px 15px; background: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer; }}
            .copy-btn:hover {{ background: #0056b3; }}
            pre {{ background: #f8f9fa; padding: 20px; border-radius: 5px; overflow-x: auto; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>API Credentials for {voice_name}</h1>
            
            <div class="field">
                <label>Voice ID:</label>
                <input type="text" id="voiceId" value="{voice_id}" readonly>
                <button class="copy-btn" onclick="copyToClipboard('voiceId')">Copy</button>
            </div>
            
            <div class="field">
                <label>API Key:</label>
                <input type="text" id="apiKey" value="{api_key}" readonly>
                <button class="copy-btn" onclick="copyToClipboard('apiKey')">Copy</button>
            </div>
            
            <h2>Usage Example</h2>
            <pre>curl -X POST http://localhost:5000/api/tts \\\n  -H "Authorization: Bearer {api_key}" \\\n  -H "Content-Type: application/json" \\\n  -d '{{
    "voice_id": "{voice_id}",
    "text": "Your text here"
  }}'</pre>
        </div>
        
        <script>
            function copyToClipboard(elementId) {{
                const element = document.getElementById(elementId);
                element.select();
                document.execCommand('copy');
                alert('Copied to clipboard!');
            }}
        </script>
    </body>
    </html>
    '''
    
    return html_content

@app.route('/get_voices', methods=['GET'])
def get_voices():
    try:
        voices = db.get_all_voices()
        for voice in voices:
            voice['audio_exists'] = os.path.exists(voice['audio_path'])
        
        predefined = [v for v in voices if v['is_predefined']]
        custom = [v for v in voices if not v['is_predefined']]
        
        return jsonify({
            'predefined_voices': predefined,
            'custom_voices': custom
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/delete_voice/<int:voice_id>', methods=['DELETE'])
def delete_voice(voice_id):
    try:
        voice = db.get_voice_by_id(voice_id)
        if not voice:
            return jsonify({'error': 'Voice not found'}), 404
        
        if voice['is_predefined']:
            return jsonify({'error': 'Cannot delete predefined voices'}), 403
        
        if os.path.exists(voice['audio_path']):
            os.remove(voice['audio_path'])
        if os.path.exists(voice['text_path']):
            os.remove(voice['text_path'])
        
        db.delete_voice(voice_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/generate_speech_with_voice', methods=['POST'])
def generate_speech_with_voice():
    data = request.json
    voice_name = data.get('voice_name')
    input_text = data.get('input_text')
    
    if not all([voice_name, input_text]):
        return jsonify({'error': 'Missing voice_name or input_text'}), 400
    
    try:
        # Get voice from database
        voice = db.get_voice_by_name(voice_name)
        if not voice:
            return jsonify({'error': 'Voice not found'}), 404
        
        # Check if audio file exists
        if not os.path.exists(voice['audio_path']):
            return jsonify({'error': f'Audio file not found for {voice_name}. Please upload the audio file.'}), 404
        
        # Read reference text
        with open(voice['text_path'], 'r') as f:
            ref_text = f.read().strip()
        
        # Get TTS instance
        tts_instance = get_tts()
        
        # Encode reference once
        ref_codes = tts_instance.encode_reference(voice['audio_path'])
        
        # Check if text needs chunking (split for 15-second segments)
        word_count = len(input_text.split())
        estimated_duration = word_count / 2.2  # Conservative estimate
        
        if estimated_duration > 15:  # If estimated duration > 15 seconds
            chunks = chunk_text_by_duration(input_text, target_duration_seconds=15)
            audio_segments = []
            
            for i, chunk in enumerate(chunks):
                wav_chunk = tts_instance.infer(chunk, ref_codes, ref_text)
                audio_segments.append(wav_chunk)
                
                import gc
                gc.collect()
                
                if i < len(chunks) - 1:
                    silence = np.zeros(int(0.3 * 24000))
                    audio_segments.append(silence)
            
            wav = np.concatenate(audio_segments)
        else:
            wav = tts_instance.infer(input_text, ref_codes, ref_text)
        
        # Save output
        output_path = "output.mp3"
        wav_path = "temp_output.wav"
        
        sf.write(wav_path, wav, 24000)
        
        # Convert to MP3
        audio = AudioSegment.from_wav(wav_path)
        audio.export(output_path, format="mp3", bitrate="192k")
        
        os.remove(wav_path)
        
        response = jsonify({'output_path': output_path})
        response.headers['Cache-Control'] = 'no-cache'
        return response
    
    except Exception as e:
        import traceback
        print(f"Error in generate_speech_with_voice: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tts', methods=['POST'])
def api_tts():
    data = request.json
    voice_id = data.get('voice_id')
    input_text = data.get('text')
    output_dir = data.get('output_dir', 'api_outputs')
    
    if not voice_id or not input_text:
        return jsonify({'error': 'Missing voice_id or text parameter'}), 400
    
    try:
        voice = db.get_voice_by_voice_id(voice_id)
        if not voice:
            return jsonify({'error': 'Voice not found'}), 404
        
        if not os.path.exists(voice['audio_path']):
            return jsonify({'error': 'Voice audio file not found'}), 404
        
        os.makedirs(output_dir, exist_ok=True)
        
        with open(voice['text_path'], 'r') as f:
            ref_text = f.read().strip()
        
        tts_instance = get_tts()
        ref_codes = tts_instance.encode_reference(voice['audio_path'])
        
        word_count = len(input_text.split())
        estimated_duration = word_count / 2.2
        
        if estimated_duration > 15:
            chunks = chunk_text_by_duration(input_text, target_duration_seconds=15)
            audio_segments = []
            
            for i, chunk in enumerate(chunks):
                wav_chunk = tts_instance.infer(chunk, ref_codes, ref_text)
                audio_segments.append(wav_chunk)
                
                import gc
                gc.collect()
                
                if i < len(chunks) - 1:
                    silence = np.zeros(int(0.3 * 24000))
                    audio_segments.append(silence)
            
            wav = np.concatenate(audio_segments)
        else:
            wav = tts_instance.infer(input_text, ref_codes, ref_text)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_filename = f"tts_output_{timestamp}.wav"
        output_path = os.path.join(output_dir, output_filename)
        
        sf.write(output_path, wav, 24000)
        
        return jsonify({
            'success': True,
            'audio_path': output_path,
            'audio_url': f'http://localhost:5000/download/{output_path}',
            'voice_id': voice_id,
            'output_directory': output_dir
        })
    
    except Exception as e:
        import traceback
        print(f"Error in api_tts: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Load existing voice data if available
    if os.path.exists('voice_store.json'):
        try:
            with open('voice_store.json', 'r') as f:
                stored_data = json.load(f)
                voice_store.update(stored_data.get('voices', {}))
                api_keys.update(stored_data.get('api_keys', {}))
        except:
            pass
    
    app.run(debug=True, host='0.0.0.0', port=5000)