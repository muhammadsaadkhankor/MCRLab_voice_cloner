from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import soundfile as sf
import whisper
try:
    import torch
except ImportError:
    torch = None
from neuttsair.neutts import NeuTTSAir
import uuid
from datetime import datetime
from pydub import AudioSegment
import json
import hashlib
import numpy as np
from database import VoiceDatabase
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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
        print("[DEBUG] Starting TTS model loading...")
        print(f"[DEBUG] Current working directory: {os.getcwd()}")
        print(f"[DEBUG] CUDA available: {torch.cuda.is_available() if torch else 'torch not imported'}")
        
        # Set cache directory for models
        os.environ['HF_HOME'] = '/root/.cache/huggingface'
        
        try:
            print("[DEBUG] Attempting CPU loading (Docker optimized)...")
            tts = NeuTTSAir(
                backbone_repo="neuphonic/neutts-air-q4-gguf",
                backbone_device="cuda",
                codec_repo="neuphonic/neucodec",
                codec_device="cuda"
            )
            print("[DEBUG] ✅ TTS model loaded successfully on CPU")
        except Exception as e:
            print(f"[DEBUG] ❌ TTS loading failed: {type(e).__name__}: {e}")
            print(f"[DEBUG] Full error: {str(e)}")
            import traceback
            print(f"[DEBUG] Traceback: {traceback.format_exc()}")
            return None
    else:
        print("[DEBUG] TTS model already loaded")
    return tts

@app.route('/upload_reference', methods=['POST'])
def upload_reference():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file'}), 400
    
    audio_file = request.files['audio']
    
    # Use fixed filenames that get overwritten
    temp_path = f"temp_reference{os.path.splitext(audio_file.filename)[1]}"
    audio_path = "samples/reference.wav"
    text_path = "samples/reference.txt"
    
    # Save temporary file
    audio_file.save(temp_path)
    
    try:
        if temp_path.lower().endswith('.wav'):
            # If already WAV, just move it
            if os.path.exists(audio_path):
                os.remove(audio_path)
            os.rename(temp_path, audio_path)
        else:
            # Convert MP3/other formats to WAV
            audio = AudioSegment.from_file(temp_path)
            audio = audio.set_channels(1)  # Convert to mono
            audio = audio.set_frame_rate(24000)  # Set sample rate
            audio.export(audio_path, format="wav")
            os.remove(temp_path)  # Clean up temp file
        
        # Transcribe audio
        result = whisper_model.transcribe(audio_path)
        transcript = result["text"].strip()
        
        # Save transcript (overwrite existing)
        with open(text_path, 'w') as f:
            f.write(transcript)
        
        return jsonify({
            'audio_path': audio_path,
            'text_path': text_path,
            'transcript': transcript,
            'ref_id': 'reference'
        })
    
    except Exception as e:
        # Clean up files on error
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({'error': f'Audio processing failed: {str(e)}'}), 500

def chunk_text_by_duration(text, max_words_per_chunk=40):
    """Split text into chunks for ~15 second segments (assuming ~2.5 words per second)"""
    words = text.split()
    chunks = []
    
    for i in range(0, len(words), max_words_per_chunk):
        chunk = ' '.join(words[i:i + max_words_per_chunk])
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
        if word_count > 40:  # ~15 seconds at 2.5 words/second
            chunks = chunk_text_by_duration(input_text)
            print(f"Word count: {word_count}, Split into {len(chunks)} chunks")
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
        
        # Save as WAV directly
        output_path = "output.wav"
        
        print(f"Saving audio file: {len(wav)} samples, {len(wav)/24000:.2f} seconds")
        sf.write(output_path, wav, 24000)
        
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

@app.route('/create_voice_api', methods=['POST'])
def create_voice_api():
    data = request.json
    audio_path = data.get('audio_path')
    text_path = data.get('text_path')
    voice_name = data.get('voice_name')
    
    if not audio_path or not text_path:
        return jsonify({'error': 'Missing audio or text path'}), 400
    
    try:
        # Generate voice ID and API key
        if voice_name:
            # For predefined voices, use consistent voice ID based on name
            voice_id = f"voice_{voice_name.lower().replace(' ', '_')}"
        else:
            # For custom voices, generate ElevenLabs-style ID
            voice_id = f"voice_{uuid.uuid4().hex[:8]}_{uuid.uuid4().hex[:4]}"
            
        # Use a master API key for all voices
        api_key = "mcr_master_api_key_2024"
        
        # Store voice data
        voice_store[voice_id] = {
            'audio_path': audio_path,
            'text_path': text_path,
            'voice_name': voice_name or 'Custom Voice',
            'created_at': datetime.now().isoformat()
        }
        
        # Store API key mapping
        if api_key not in api_keys:
            api_keys[api_key] = []
        if voice_id not in api_keys[api_key]:
            api_keys[api_key].append(voice_id)
        
        return jsonify({
            'voice_id': voice_id,
            'api_key': api_key,
            'voice_name': voice_name or 'Custom Voice'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/create_predefined_apis', methods=['POST'])
def create_predefined_apis():
    """Create APIs for all predefined voices"""
    try:
        voices = db.get_all_voices()
        created_apis = []
        api_key = "mcr_master_api_key_2024"
        
        for voice in voices:
            if voice['is_predefined'] and os.path.exists(voice['audio_path']):
                voice_id = f"voice_{voice['name'].lower().replace(' ', '_')}"
                
                # Store voice data
                voice_store[voice_id] = {
                    'audio_path': voice['audio_path'],
                    'text_path': voice['text_path'],
                    'voice_name': voice['name'],
                    'created_at': datetime.now().isoformat()
                }
                
                # Store API key mapping
                if api_key not in api_keys:
                    api_keys[api_key] = []
                if voice_id not in api_keys[api_key]:
                    api_keys[api_key].append(voice_id)
                
                created_apis.append({
                    'voice_id': voice_id,
                    'voice_name': voice['name'],
                    'api_key': api_key
                })
        
        return jsonify({
            'created_apis': created_apis,
            'master_api_key': api_key
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get_voices', methods=['GET'])
def get_voices():
    try:
        voices = db.get_all_voices()
        # Check if audio files exist for all voices
        for voice in voices:
            voice['audio_exists'] = os.path.exists(voice['audio_path'])
        return jsonify({'voices': voices})
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
        if word_count > 40:
            chunks = chunk_text_by_duration(input_text)
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
        
        # Save output as WAV
        output_path = "output.wav"
        
        sf.write(output_path, wav, 24000)
        
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
    # Check authorization
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Missing or invalid authorization'}), 401
    
    api_key = auth_header.split(' ')[1]
    if api_key not in api_keys:
        return jsonify({'error': 'Invalid API key'}), 401
    
    data = request.json
    input_text = data.get('text')
    requested_voice_id = data.get('voice_id')
    output_path = data.get('output_path')  # Optional custom output path
    
    if not input_text:
        return jsonify({'error': 'Missing text parameter'}), 400
        
    if not requested_voice_id:
        return jsonify({'error': 'Missing voice_id parameter'}), 400
    
    # Check if voice ID is available for this API key
    available_voices = api_keys[api_key]
    if requested_voice_id not in available_voices:
        return jsonify({'error': f'Voice ID {requested_voice_id} not available for this API key'}), 403
    
    if requested_voice_id not in voice_store:
        return jsonify({'error': 'Voice not found in store'}), 404
    
    try:
        voice_data = voice_store[requested_voice_id]
        
        # Read reference text
        with open(voice_data['text_path'], 'r') as f:
            ref_text = f.read().strip()
        
        # Get TTS instance
        tts_instance = get_tts()
        
        # Generate speech with chunking for long text
        ref_codes = tts_instance.encode_reference(voice_data['audio_path'])
        
        # Check if text needs chunking
        word_count = len(input_text.split())
        if word_count > 40:
            chunks = chunk_text_by_duration(input_text)
            audio_segments = []
            
            for i, chunk in enumerate(chunks):
                wav_chunk = tts_instance.infer(chunk, ref_codes, ref_text)
                audio_segments.append(wav_chunk)
                
                if i < len(chunks) - 1:
                    silence = np.zeros(int(0.3 * 24000))
                    audio_segments.append(silence)
            
            wav = np.concatenate(audio_segments)
        else:
            wav = tts_instance.infer(input_text, ref_codes, ref_text)
        
        # Determine output path
        if output_path:
            # Use custom path, ensure it ends with .wav
            if not output_path.lower().endswith('.wav'):
                output_path += '.wav'
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            final_output_path = output_path
        else:
            # Default behavior - save in project directory
            timestamp = int(datetime.now().timestamp())
            final_output_path = f"api_output_{requested_voice_id}_{timestamp}.wav"
        
        # Save as WAV directly
        sf.write(final_output_path, wav, 24000)
        
        return jsonify({
            'success': True,
            'output_path': final_output_path,
            'audio_url': f'http://localhost:4000/download/{os.path.basename(final_output_path)}' if not output_path else None,
            'voice_id': requested_voice_id,
            'voice_name': voice_data['voice_name'],
            'text_length': len(input_text),
            'word_count': word_count
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/voices', methods=['GET'])
def api_list_voices():
    """List available voices for API usage"""
    # Check authorization
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Missing or invalid authorization'}), 401
    
    api_key = auth_header.split(' ')[1]
    if api_key not in api_keys:
        return jsonify({'error': 'Invalid API key'}), 401
    
    try:
        available_voices = api_keys[api_key]
        voices_info = []
        
        for voice_id in available_voices:
            if voice_id in voice_store:
                voice_data = voice_store[voice_id]
                voices_info.append({
                    'voice_id': voice_id,
                    'voice_name': voice_data['voice_name'],
                    'created_at': voice_data['created_at']
                })
        
        return jsonify({
            'voices': voices_info,
            'total_voices': len(voices_info)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/save_custom_voice', methods=['POST'])
def save_custom_voice():
    data = request.json
    voice_name = data.get('voice_name')
    audio_path = data.get('audio_path')
    text_path = data.get('text_path')
    transcript = data.get('transcript')
    
    if not all([voice_name, audio_path, text_path]):
        return jsonify({'error': 'Missing required parameters'}), 400
    
    try:
        # Generate unique voice ID
        voice_id = f"voice_{uuid.uuid4().hex[:8]}_{uuid.uuid4().hex[:4]}"
        
        # Save to database
        db.add_voice(voice_name, audio_path, text_path, is_predefined=False, voice_id=voice_id)
        
        # Add to voice store for API usage
        voice_store[voice_id] = {
            'audio_path': audio_path,
            'text_path': text_path,
            'voice_name': voice_name,
            'created_at': datetime.now().isoformat()
        }
        
        # Add to master API key
        api_key = "mcr_master_api_key_2024"
        if api_key not in api_keys:
            api_keys[api_key] = []
        if voice_id not in api_keys[api_key]:
            api_keys[api_key].append(voice_id)
        
        return jsonify({
            'success': True,
            'voice_id': voice_id,
            'voice_name': voice_name
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get_custom_voices', methods=['GET'])
def get_custom_voices():
    try:
        voices = db.get_all_voices()
        custom_voices = []
        
        for voice in voices:
            if not voice['is_predefined']:
                # Get voice_id from voice_store or generate if missing
                voice_id = None
                for vid, vdata in voice_store.items():
                    if vdata['voice_name'] == voice['name'] and vdata['audio_path'] == voice['audio_path']:
                        voice_id = vid
                        break
                
                if not voice_id:
                    voice_id = f"voice_{uuid.uuid4().hex[:8]}_{uuid.uuid4().hex[:4]}"
                    voice_store[voice_id] = {
                        'audio_path': voice['audio_path'],
                        'text_path': voice['text_path'],
                        'voice_name': voice['name'],
                        'created_at': datetime.now().isoformat()
                    }
                
                custom_voices.append({
                    'id': voice['id'],
                    'name': voice['name'],
                    'voice_id': voice_id,
                    'audio_path': voice['audio_path'],
                    'text_path': voice['text_path']
                })
        
        return jsonify({'voices': custom_voices})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/create_api_key', methods=['POST'])
def create_api_key():
    data = request.json
    api_name = data.get('api_name')
    
    if not api_name:
        return jsonify({'error': 'Missing api_name'}), 400
    
    try:
        # Generate API key with sk_ prefix
        api_key = f"sk_{uuid.uuid4().hex[:32]}"
        
        # Ensure predefined voices are in voice_store
        predefined_voices = [
            ('voice_professor_abed', 'Professor Abed', 'samples/professor_abed.wav', 'samples/professor_abed.txt'),
            ('voice_christine', 'Christine', 'samples/christine.wav', 'samples/christine.txt'),
            ('voice_saad', 'Saad', 'samples/saad.wav', 'samples/saad.txt')
        ]
        
        for voice_id, voice_name, audio_path, text_path in predefined_voices:
            if voice_id not in voice_store and os.path.exists(audio_path):
                voice_store[voice_id] = {
                    'audio_path': audio_path,
                    'text_path': text_path,
                    'voice_name': voice_name,
                    'created_at': datetime.now().isoformat()
                }
        
        # Store API key with access to all voices
        api_keys[api_key] = list(voice_store.keys())
        
        return jsonify({
            'api_name': api_name,
            'api_key': api_key,
            'created_at': datetime.now().isoformat(),
            'voice_count': len(api_keys[api_key])
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500



@app.route('/transcribe_audio', methods=['POST'])
def transcribe_audio():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file'}), 400
    
    audio_file = request.files['audio']
    
    try:
        # Save temporary audio file
        temp_path = f"temp_transcribe_{uuid.uuid4().hex[:8]}.wav"
        audio_file.save(temp_path)
        
        # Convert to WAV if needed
        if not temp_path.lower().endswith('.wav'):
            audio = AudioSegment.from_file(temp_path)
            audio = audio.set_channels(1)
            audio = audio.set_frame_rate(24000)
            wav_path = temp_path.replace(os.path.splitext(temp_path)[1], '.wav')
            audio.export(wav_path, format="wav")
            os.remove(temp_path)
            temp_path = wav_path
        
        # Transcribe audio
        result = whisper_model.transcribe(temp_path)
        transcript = result["text"].strip()
        
        # Clean up
        os.remove(temp_path)
        
        return jsonify({'transcript': transcript})
    
    except Exception as e:
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({'error': str(e)}), 500









def extract_text_from_pdf(pdf_file):
    """Extract text content from PDF file"""
    if PyPDF2 is None:
        return "PyPDF2 not installed. Please install with: pip install PyPDF2"
    
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        print(f"Error extracting PDF text: {e}")
        return None

def generate_cv_summary(cv_text):
    """Generate CV summary using GPT-4"""
    try:
        api_key = os.getenv('OPENROUTER_API_KEY')
        if not api_key:
            return "CV contains relevant experience and skills."
        
        prompt = f"Summarize this CV in 2-3 sentences, highlighting key skills and experience:\n\n{cv_text[:2000]}"
        
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "openai/gpt-4-turbo",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 150,
                "temperature": 0.7
            }
        )
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return "CV contains relevant experience and skills."
            
    except Exception as e:
        print(f"Error generating CV summary: {e}")
        return "CV processed successfully."

def generate_personalized_interview_questions(cv_text):
    """Generate 3 technical interview questions based on CV content using GPT-4"""
    try:
        api_key = os.getenv('OPENROUTER_API_KEY')
        if not api_key:
            return [
                "Explain a complex technical problem you solved and your approach to solving it.",
                "Describe the most challenging technical project from your CV and the technologies you used.",
                "Walk me through your experience with the key programming languages or frameworks mentioned in your CV."
            ]
        
        prompt = f"""Carefully analyze this CV and extract SPECIFIC technologies mentioned in:
1. THESIS/RESEARCH projects
2. WORK EXPERIENCE projects
3. TECHNICAL SKILLS section
4. PROJECT descriptions

Look for exact technical terms like:
- Programming languages, frameworks, libraries
- Medical procedures, drugs, diagnostic methods
- Engineering tools, software, methodologies
- Scientific techniques, equipment, algorithms
- Business tools, methodologies, systems

Then generate 3 HIGHLY TECHNICAL questions about the SPECIFIC technologies found:

Format: Ask about internal workings, not general experience
Examples:
- If "Python" found: "Explain Python's GIL and its impact on multithreading"
- If "React" found: "How does React's reconciliation algorithm work?"
- If "PCR" found: "Explain the three steps of PCR amplification cycle"
- If "AutoCAD" found: "How does parametric modeling work in CAD?"
- If "HPLC" found: "Explain the separation mechanism in HPLC"

CV Content:
{cv_text[:3000]}

Extract specific technologies, then ask technical questions about HOW they work internally."""
        
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "openai/gpt-4-turbo",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 500,
                "temperature": 0.8
            }
        )
        
        if response.status_code == 200:
            questions_text = response.json()['choices'][0]['message']['content']
            # Split into individual questions and clean them
            questions = []
            for line in questions_text.split('\n'):
                line = line.strip()
                # Remove numbering and clean up
                if line and ('?' in line or len(line) > 30):
                    # Remove common prefixes like "1.", "Q1:", etc.
                    line = line.replace('1.', '').replace('2.', '').replace('3.', '')
                    line = line.replace('Q1:', '').replace('Q2:', '').replace('Q3:', '')
                    line = line.replace('Question 1:', '').replace('Question 2:', '').replace('Question 3:', '')
                    line = line.strip()
                    if line and len(line) > 20:
                        questions.append(line)
            
            # Ensure we have exactly 3 questions
            if len(questions) >= 3:
                return questions[:3]
            else:
                # Technical fallback questions
                return [
                    "Explain a key technical concept from your field of expertise.",
                    "What is the most important methodology or technique you use in your work?",
                    "How do you approach problem-solving in your professional domain?"
                ]
        else:
            return [
                "Explain a key technical concept from your field of expertise.",
                "What is the most important methodology or technique you use in your work?",
                "How do you approach problem-solving in your professional domain?"
            ]
            
    except Exception as e:
        print(f"Error generating technical questions: {e}")
        return [
            "Explain a key technical concept from your field of expertise.",
            "What is the most important methodology or technique you use in your work?",
            "How do you approach problem-solving in your professional domain?"
        ]

def evaluate_interview_answers(cv_text, questions, answers):
    """Generate detailed evaluation report using GPT-4"""
    try:
        api_key = os.getenv('OPENROUTER_API_KEY')
        if not api_key:
            return "Interview completed successfully. Good responses overall."
        
        qa_pairs = "\n\n".join([f"Q{i+1}: {questions[i]}\nA{i+1}: {answers[i]}" for i in range(len(answers))])
        
        prompt = f"""Generate a detailed interview evaluation report based on CV and Q&A:

CV Summary: {cv_text[:1000]}

Interview Q&A:
{qa_pairs}

Provide detailed analysis in this format:

**OVERALL SCORE: X/10**

**STRENGTHS:**
- Specific strength 1 with example
- Specific strength 2 with example
- Specific strength 3 with example

**WEAKNESSES:**
- Specific weakness 1 with improvement suggestion
- Specific weakness 2 with improvement suggestion
- Specific weakness 3 with improvement suggestion

**QUESTION-BY-QUESTION ANALYSIS:**
Q1: [Brief assessment of answer quality]
Q2: [Brief assessment of answer quality]
Q3: [Brief assessment of answer quality]

**RECOMMENDATIONS:**
- Specific recommendation 1
- Specific recommendation 2
- Specific recommendation 3"""
        
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "openai/gpt-4-turbo",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 800,
                "temperature": 0.7
            }
        )
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return "Interview completed. Good responses overall."
            
    except Exception as e:
        print(f"Error evaluating answers: {e}")
        return "Interview completed successfully."

def generate_pdf_report(candidate_name, questions, answers, evaluation, session_id):
    """Generate PDF report using reportlab"""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        
        filename = f"interview_report_{session_id}.pdf"
        doc = SimpleDocTemplate(filename, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Title
        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=18, spaceAfter=30)
        story.append(Paragraph(f"Interview Report - {candidate_name}", title_style))
        story.append(Spacer(1, 12))
        
        # Questions and Answers
        story.append(Paragraph("Interview Questions & Answers", styles['Heading2']))
        for i, (q, a) in enumerate(zip(questions, answers)):
            story.append(Paragraph(f"<b>Question {i+1}:</b> {q}", styles['Normal']))
            story.append(Paragraph(f"<b>Answer:</b> {a}", styles['Normal']))
            story.append(Spacer(1, 12))
        
        # Evaluation
        story.append(Paragraph("Detailed Evaluation", styles['Heading2']))
        eval_lines = evaluation.split('\n')
        for line in eval_lines:
            if line.strip():
                story.append(Paragraph(line, styles['Normal']))
                story.append(Spacer(1, 6))
        
        doc.build(story)
        return filename
        
    except ImportError:
        print("reportlab not installed, generating text report")
        filename = f"interview_report_{session_id}.txt"
        with open(filename, 'w') as f:
            f.write(f"Interview Report - {candidate_name}\n\n")
            f.write("Questions & Answers:\n")
            for i, (q, a) in enumerate(zip(questions, answers)):
                f.write(f"Q{i+1}: {q}\nA{i+1}: {a}\n\n")
            f.write(f"Evaluation:\n{evaluation}")
        return filename
    except Exception as e:
        print(f"Error generating PDF: {e}")
        return None

def get_gpt4_response(user_message):
    """Generate AI response using GPT-4 via OpenRouter"""
    try:
        api_key = os.getenv('OPENROUTER_API_KEY')
        print(f"[DEBUG] API key exists: {bool(api_key)}")
        
        if not api_key:
            print("[DEBUG] No API key found")
            return "I appreciate your response. Let me think about that for a moment."
        
        # Create conversation context
        context = "You are Professor Abed, a helpful AI assistant. Respond naturally and helpfully to whatever the user asks. Keep responses conversational and under 50 words."
        
        messages = [
            {"role": "system", "content": context},
            {"role": "user", "content": user_message}
        ]
        
        print(f"[DEBUG] Calling OpenRouter API with message: {user_message}")
        
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:4000",
                "X-Title": "Voice Cloner App"
            },
            json={
                "model": "openai/gpt-4-turbo",
                "messages": messages,
                "max_tokens": 100,
                "temperature": 0.7
            },
            timeout=30
        )
        
        print(f"[DEBUG] OpenRouter response status: {response.status_code}")
        print(f"[DEBUG] OpenRouter response text: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"[DEBUG] OpenRouter JSON response: {result}")
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0]['message']['content']
                print(f"[DEBUG] Extracted content: {content}")
                return content
            else:
                print("[DEBUG] No choices in response")
                return "That's interesting! Tell me more about that."
        else:
            print(f"[DEBUG] Non-200 status: {response.status_code} - {response.text}")
            return "That's interesting! Tell me more about that."
            
    except Exception as e:
        print(f"[DEBUG] Exception in get_gpt4_response: {e}")
        import traceback
        print(f"[DEBUG] Traceback: {traceback.format_exc()}")
        return "I find that fascinating. What else would you like to discuss?"



@app.route('/process_cv_interview', methods=['POST'])
def process_cv_interview():
    if 'cv' not in request.files:
        return jsonify({'error': 'No CV file uploaded'}), 400
    
    cv_file = request.files['cv']
    candidate_name = request.form.get('candidate_name')
    selected_agent = request.form.get('selected_agent', 'Professor Abed')
    
    if not candidate_name:
        return jsonify({'error': 'Candidate name required'}), 400
    
    try:
        # Extract text from PDF
        cv_text = extract_text_from_pdf(cv_file)
        if not cv_text:
            return jsonify({'error': 'Could not extract text from CV'}), 400
        
        # Generate CV summary and personalized questions
        cv_summary = generate_cv_summary(cv_text)
        questions = generate_personalized_interview_questions(cv_text)
        
        # Store CV text for later evaluation
        session_id = str(uuid.uuid4())
        interview_sessions[session_id] = {
            'cv_text': cv_text,
            'questions': questions,
            'answers': [],
            'candidate_name': candidate_name
        }
        
        # Generate audio for first question
        first_question_audio = None
        if questions:
            voice = db.get_voice_by_name('Professor Abed')
            if voice and os.path.exists(voice['audio_path']):
                with open(voice['text_path'], 'r') as f:
                    ref_text = f.read().strip()
                
                tts_instance = get_tts()
                ref_codes = tts_instance.encode_reference(voice['audio_path'])
                wav = tts_instance.infer(questions[0], ref_codes, ref_text)
                
                output_path = "cv_question.mp3"
                wav_path = "temp_first_question.wav"
                
                sf.write(wav_path, wav, 24000)
                audio = AudioSegment.from_wav(wav_path)
                audio.export(output_path, format="mp3", bitrate="192k")
                os.remove(wav_path)
                
                first_question_audio = f'http://localhost:4000/download/{output_path}'
        
        return jsonify({
            'session_id': session_id,
            'cv_summary': cv_summary,
            'questions': questions,
            'candidate_name': candidate_name,
            'selected_agent': selected_agent
        })
    
    except Exception as e:
        return jsonify({'error': f'CV processing failed: {str(e)}'}), 500

@app.route('/generate_question_audio', methods=['POST'])
def generate_question_audio():
    data = request.json
    question = data.get('question')
    
    if not question:
        return jsonify({'error': 'Question text required'}), 400
    
    try:
        voice = db.get_voice_by_name('Professor Abed')
        if voice and os.path.exists(voice['audio_path']):
            with open(voice['text_path'], 'r') as f:
                ref_text = f.read().strip()
            
            tts_instance = get_tts()
            ref_codes = tts_instance.encode_reference(voice['audio_path'])
            wav = tts_instance.infer(question, ref_codes, ref_text)
            
            output_path = "cv_question_audio.mp3"
            wav_path = "temp_question.wav"
            
            sf.write(wav_path, wav, 24000)
            audio = AudioSegment.from_wav(wav_path)
            audio.export(output_path, format="mp3", bitrate="192k")
            os.remove(wav_path)
            
            return jsonify({
                'audio_url': f'http://localhost:4000/download/{output_path}'
            })
        
        return jsonify({'audio_url': None})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/evaluate_interview', methods=['POST'])
def evaluate_interview():
    try:
        data = request.json
        print(f"[DEBUG] Received data: {data}")
        
        session_id = data.get('session_id') if data else None
        answers = data.get('answers', []) if data else []
        questions = data.get('questions', []) if data else []
        
        print(f"[DEBUG] Session ID: {session_id}")
        print(f"[DEBUG] Available sessions: {list(interview_sessions.keys())}")
        print(f"[DEBUG] Questions count: {len(questions)}")
        print(f"[DEBUG] Answers count: {len(answers)}")
        
        if not session_id:
            return jsonify({'error': 'Missing session_id'}), 400
            
        if session_id not in interview_sessions:
            return jsonify({'error': f'Session {session_id} not found'}), 400
        
        session_data = interview_sessions[session_id]
        cv_text = session_data['cv_text']
        candidate_name = session_data['candidate_name']
        
        evaluation = evaluate_interview_answers(cv_text, questions, answers)
        
        # Generate PDF report
        pdf_filename = generate_pdf_report(candidate_name, questions, answers, evaluation, session_id)
        
        return jsonify({
            'evaluation': evaluation,
            'pdf_report': pdf_filename
        })
    
    except Exception as e:
        print(f"[DEBUG] Error in evaluate_interview: {str(e)}")
        import traceback
        print(f"[DEBUG] Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Load predefined voices into voice_store
    predefined_voices = [
        ('voice_professor_abed', 'Professor Abed', 'samples/professor_abed.wav', 'samples/professor_abed.txt'),
        ('voice_christine', 'Christine', 'samples/christine.wav', 'samples/christine.txt'),
        ('voice_saad', 'Saad', 'samples/saad.wav', 'samples/saad.txt')
    ]
    
    for voice_id, voice_name, audio_path, text_path in predefined_voices:
        if os.path.exists(audio_path):
            voice_store[voice_id] = {
                'audio_path': audio_path,
                'text_path': text_path,
                'voice_name': voice_name,
                'created_at': datetime.now().isoformat()
            }
    
    # Load existing voice data if available
    if os.path.exists('voice_store.json'):
        try:
            with open('voice_store.json', 'r') as f:
                stored_data = json.load(f)
                voice_store.update(stored_data.get('voices', {}))
                api_keys.update(stored_data.get('api_keys', {}))
        except:
            pass
    
    app.run(debug=True, host='0.0.0.0', port=4000)