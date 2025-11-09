import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [isRecording, setIsRecording] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [refData, setRefData] = useState(null);
  const [inputText, setInputText] = useState('');
  const [outputAudio, setOutputAudio] = useState(null);
  const [loading, setLoading] = useState(false);
  const [voiceId, setVoiceId] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [showApiPanel, setShowApiPanel] = useState(false);
  const [copiedField, setCopiedField] = useState('');
  const [predefinedVoices, setPredefinedVoices] = useState([]);
  const [customVoices, setCustomVoices] = useState([]);
  const [selectedVoice, setSelectedVoice] = useState(null);
  const [voiceInputText, setVoiceInputText] = useState('');
  const [voiceOutputAudio, setVoiceOutputAudio] = useState(null);
  const [copiedVoiceId, setCopiedVoiceId] = useState(null);
  
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const fileInputRef = useRef(null);

  const startRecording = async () => {
    try {
      setSelectedVoice(null); // Clear predefined voice selection
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      chunksRef.current = [];

      mediaRecorderRef.current.ondataavailable = (event) => {
        chunksRef.current.push(event.data);
      };

      mediaRecorderRef.current.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/wav' });
        await uploadReference(blob);
      };

      mediaRecorderRef.current.start();
      setIsRecording(true);
    } catch (error) {
      alert('Error accessing microphone: ' + error.message);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const uploadReference = async (audioBlob, filename = 'reference.wav') => {
    setLoading(true);
    setSelectedVoice(null);
    const formData = new FormData();
    formData.append('audio', audioBlob, filename);
    formData.append('voice_name', 'Custom Voice');

    try {
      const response = await axios.post('http://localhost:5000/upload_reference', formData);
      setRefData({...response.data, submitted: false});
      setTranscript(response.data.transcript);
      fetchVoices();
    } catch (error) {
      alert('Error uploading reference: ' + error.message);
    }
    setLoading(false);
  };

  const submitReference = () => {
    setRefData({...refData, submitted: true});
  };

  const createAPI = () => {
    window.location.href = 'http://localhost:5000/api';
  };

  const handleFileUpload = (event) => {
    const file = event.target.files[0];
    if (file) {
      uploadReference(file, file.name);
    }
  };

  const triggerFileUpload = () => {
    fileInputRef.current.click();
  };

  const generateSpeech = async () => {
    if (!refData || !inputText) return;
    
    setLoading(true);
    try {
      const response = await axios.post('http://localhost:5000/generate_speech', {
        input_text: inputText,
        ref_audio_path: refData.audio_path,
        ref_text_path: refData.text_path
      });
      
      setOutputAudio(`http://localhost:5000/download/${response.data.output_path}?t=${Date.now()}`);
    } catch (error) {
      console.error('Full error:', error);
      const errorMsg = error.response?.data?.error || error.message;
      alert('Error generating speech: ' + errorMsg);
    }
    setLoading(false);
  };

  const copyToClipboard = (text, field) => {
    navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(''), 2000);
  };

  const copyVoiceId = (voiceId, e) => {
    e.stopPropagation();
    navigator.clipboard.writeText(voiceId);
    setCopiedVoiceId(voiceId);
    setTimeout(() => setCopiedVoiceId(null), 2000);
  };

  useEffect(() => {
    fetchVoices();
  }, []);

  const fetchVoices = async () => {
    try {
      const response = await axios.get('http://localhost:5000/get_voices');
      setPredefinedVoices(response.data.predefined_voices);
      setCustomVoices(response.data.custom_voices);
    } catch (error) {
      console.error('Error fetching voices:', error);
    }
  };

  const selectVoice = (voice) => {
    setSelectedVoice(voice);
    setVoiceInputText('');
    setVoiceOutputAudio(null);
    setRefData(null);
    setTranscript('');
    setInputText('');
    setOutputAudio(null);
  };

  const deleteVoice = async (voiceId, e) => {
    e.stopPropagation();
    if (!window.confirm('Delete this voice?')) return;
    
    try {
      await axios.delete(`http://localhost:5000/delete_voice/${voiceId}`);
      fetchVoices();
    } catch (error) {
      alert('Error deleting voice: ' + error.message);
    }
  };

  const generateVoiceSpeech = async () => {
    if (!selectedVoice || !voiceInputText) return;
    
    setLoading(true);
    try {
      const response = await axios.post('http://localhost:5000/generate_speech_with_voice', {
        voice_name: selectedVoice.name,
        input_text: voiceInputText
      });
      
      setVoiceOutputAudio(`http://localhost:5000/download/${response.data.output_path}?t=${Date.now()}`);
    } catch (error) {
      const errorMsg = error.response?.data?.error || error.message;
      alert('Error generating speech: ' + errorMsg);
    }
    setLoading(false);
  };



  return (
    <div className="App">
      {/* Header */}
      <div className="header">
        <div className="header-content">
          <div className="header-title">
            <h1>HUMAIN</h1>
            <p className="subtitle">Voice Cloning Lab</p>
          </div>
          <button 
            className="api-btn"
            onClick={createAPI}
          >
            Create API
          </button>
        </div>
      </div>

      <div className="container">
        {/* Info Banner */}
        <div className="info-banner">
          <h2 className="banner-title">VOICE CLONING STUDIO</h2>
          <p className="banner-description">
            Create AI-generated speech using your own voice. Record or upload a sample, then generate natural-sounding audio from any text.
          </p>
          
          <div className="stats-grid">
            <div className="stat-item">
              <div className="stat-number">2</div>
              <div className="stat-label">Simple Steps</div>
            </div>
            <div className="stat-item">
              <div className="stat-number">3-15s</div>
              <div className="stat-label">Voice Sample Needed</div>
            </div>
            <div className="stat-item">
              <div className="stat-number">∞</div>
              <div className="stat-label">Text Length Supported</div>
            </div>
          </div>
        </div>

        {/* Step 1: Provide Voice */}
        <div className="section">
          <div className="section-header">
            <h2>STEP 1: PROVIDE YOUR VOICE</h2>
            <p className="section-description">Record your voice or upload an audio file to create a voice profile</p>
          </div>

          <div className="voice-options">
            <button 
              className={`voice-btn ${isRecording ? 'recording' : ''}`}
              onClick={isRecording ? stopRecording : startRecording}
              disabled={loading}
            >
              <span className="btn-icon">🎤</span>
              {isRecording ? 'Stop Recording' : 'Start Recording'}
            </button>
            
            <span className="or-text">OR</span>
            
            <button 
              className="voice-btn"
              onClick={triggerFileUpload}
              disabled={loading || isRecording}
            >
              <span className="btn-icon">📤</span>
              Upload Audio (WAV/MP3)
            </button>
            
            <input
              ref={fileInputRef}
              type="file"
              accept=".wav,.mp3,audio/wav,audio/mpeg"
              onChange={handleFileUpload}
              style={{ display: 'none' }}
            />
          </div>
          
          {loading && (
            <div className="loading-message">
              <span className="spinner"></span>
              🎵 Processing audio...
            </div>
          )}
          
          {transcript && (
            <div className="transcript">
              <h3>Transcript:</h3>
              <p className="transcript-text">{transcript}</p>
              <button 
                onClick={submitReference}
                className="submit-btn"
                disabled={refData?.submitted}
              >
                {refData?.submitted ? '✓ Reference Submitted' : 'Submit Reference'}
              </button>
            </div>
          )}
        </div>

        {/* Predefined Voices Section */}
        <div className="section">
          <div className="section-header">
            <h2>PREDEFINED VOICES</h2>
            <p className="section-description">Select from our collection of pre-trained voices</p>
          </div>

          <div className="voices-grid">
            {predefinedVoices.map((voice) => (
              <div 
                key={voice.id} 
                className={`voice-card ${selectedVoice?.id === voice.id ? 'selected' : ''} ${!voice.audio_exists ? 'missing-audio' : ''}`}
                onClick={() => voice.audio_exists && selectVoice(voice)}
              >
                <div className="voice-info">
                  <h3>{voice.name}</h3>
                  <span className="voice-status predefined">Predefined</span>
                </div>
                
                {!voice.audio_exists && (
                  <div className="missing-audio-notice">
                    <p>Audio file not found</p>
                    <p className="file-path">Expected: {voice.audio_path}</p>
                  </div>
                )}
                
                {voice.audio_exists && voice.voice_id && (
                  <div className="voice-id-display">
                    <div style={{fontSize: '0.75rem', color: '#64748b', marginBottom: '0.25rem'}}>Voice ID:</div>
                    <div style={{display: 'flex', gap: '0.5rem', alignItems: 'center'}}>
                      <code style={{flex: 1, fontSize: '0.75rem', wordBreak: 'break-all'}}>{voice.voice_id}</code>
                      <button
                        className="copy-id-btn"
                        onClick={(e) => copyVoiceId(voice.voice_id, e)}
                      >
                        {copiedVoiceId === voice.voice_id ? 'Copied!' : 'Copy'}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
          
        </div>

        {/* My Voices Section */}
        {customVoices.length > 0 && (
          <div className="section">
            <div className="section-header">
              <h2>MY VOICES</h2>
              <p className="section-description">Your custom recorded or uploaded voices</p>
            </div>

            <div className="voices-grid">
              {customVoices.map((voice) => (
                <div 
                  key={voice.id} 
                  className={`voice-card ${selectedVoice?.id === voice.id ? 'selected' : ''}`}
                  onClick={() => selectVoice(voice)}
                >
                  <div className="voice-info">
                    <h3>{voice.name}</h3>
                    <span className="voice-status custom">Custom</span>
                  </div>
                  
                  <button 
                    className="delete-voice-btn"
                    onClick={(e) => deleteVoice(voice.id, e)}
                    title="Delete voice"
                  >
                    ×
                  </button>
                  
                  {voice.voice_id && (
                    <div className="voice-id-display">
                      <div style={{fontSize: '0.75rem', color: '#64748b', marginBottom: '0.25rem'}}>Voice ID:</div>
                      <div style={{display: 'flex', gap: '0.5rem', alignItems: 'center'}}>
                        <code style={{flex: 1, fontSize: '0.75rem', wordBreak: 'break-all'}}>{voice.voice_id}</code>
                        <button
                          className="copy-id-btn"
                          onClick={(e) => copyVoiceId(voice.voice_id, e)}
                        >
                          {copiedVoiceId === voice.voice_id ? 'Copied!' : 'Copy'}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Voice Generation Section */}
        {selectedVoice && (
          <div className="section">
            <div className="section-header">
              <h2>GENERATE WITH {selectedVoice.name.toUpperCase()}</h2>
              <p className="section-description">Enter text to convert using {selectedVoice.name}'s voice</p>
            </div>

            <textarea
              className="text-input"
              value={voiceInputText}
              onChange={(e) => setVoiceInputText(e.target.value)}
              placeholder={`Enter text to convert using ${selectedVoice.name}'s voice...`}
              rows={6}
            />
            
            <div className="char-counter">
              {voiceInputText.length} characters
            </div>

            <button 
              className="generate-btn"
              onClick={generateVoiceSpeech} 
              disabled={!voiceInputText || loading}
            >
              {loading ? (
                <>
                  <span className="spinner"></span>
                  Generating...
                </>
              ) : (
                <>
                  <span className="btn-icon">▶️</span>
                  Generate with {selectedVoice.name}
                </>
              )}
            </button>
            
            {voiceOutputAudio && (
              <div className="output">
                <h3>
                  <span className="pulse-dot"></span>
                  Generated Audio - {selectedVoice.name}
                </h3>
                <div className="audio-container">
                  <audio controls src={voiceOutputAudio} />
                </div>
                <a href={voiceOutputAudio} download className="download-btn">
                  <span className="btn-icon">⬇️</span>
                  Download Audio
                </a>
              </div>
            )}
          </div>
        )}

        {/* Step 2: Generate Speech */}
        {refData && refData.submitted && (
          <div className="section">
            <div className="section-header">
              <h2>STEP 2: GENERATE SPEECH</h2>
              <p className="section-description">Enter any text to convert to speech using your voice profile</p>
            </div>

            <div className="reference-info">
              <strong>Reference ID:</strong> {refData.ref_id}
            </div>

            <textarea
              className="text-input"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="Enter text to convert to speech... (no limit - long text will be chunked automatically)"
              rows={6}
            />
            
            <div className="char-counter">
              {inputText.length} characters
            </div>

            <button 
              className="generate-btn"
              onClick={generateSpeech} 
              disabled={!inputText || loading}
            >
              {loading ? (
                <>
                  <span className="spinner"></span>
                  Generating...
                </>
              ) : (
                <>
                  <span className="btn-icon">▶️</span>
                  Generate Speech
                </>
              )}
            </button>
            
            {outputAudio && (
              <div className="output">
                <h3>
                  <span className="pulse-dot"></span>
                  Generated Audio
                </h3>
                <div className="audio-container">
                  <audio controls src={outputAudio} />
                </div>
                <a href={outputAudio} download className="download-btn">
                  <span className="btn-icon">⬇️</span>
                  Download Audio
                </a>
              </div>
            )}
          </div>
        )}
        
        {/* API Credentials Panel */}
        {showApiPanel && (
          <div className="section api-section">
            <h2>🔑 API CREDENTIALS</h2>
            
            <div className="api-fields">
              <div className="api-field">
                <label>Voice ID</label>
                <div className="input-group">
                  <input type="text" value={voiceId} readOnly />
                  <button 
                    className="copy-btn"
                    onClick={() => copyToClipboard(voiceId, 'voiceId')}
                  >
                    {copiedField === 'voiceId' ? '✓' : '📋'}
                  </button>
                </div>
              </div>
              
              <div className="api-field">
                <label>API Key (sk_...)</label>
                <div className="input-group">
                  <input type="text" value={apiKey} readOnly />
                  <button 
                    className="copy-btn"
                    onClick={() => copyToClipboard(apiKey, 'apiKey')}
                  >
                    {copiedField === 'apiKey' ? '✓' : '📋'}
                  </button>
                </div>
              </div>
            </div>
            
            <div className="api-usage">
              <h3>📖 How to Use API</h3>
              <div className="usage-section">
                <h4>Basic Usage:</h4>
                <pre>{`curl -X POST http://localhost:5000/api/tts \\
  -H "Authorization: Bearer ${apiKey}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "voice_id": "${voiceId}",
    "text": "Your text here"
  }'`}</pre>
              </div>
              
              <div className="usage-section">
                <h4>With Custom Output Directory:</h4>
                <pre>{`curl -X POST http://localhost:5000/api/tts \\
  -H "Authorization: Bearer ${apiKey}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "voice_id": "${voiceId}",
    "text": "Your text here",
    "output_dir": "my_audio_files"
  }'`}</pre>
              </div>
              
              <div className="usage-section">
                <h4>Response Format:</h4>
                <pre>{`{
  "success": true,
  "audio_path": "api_outputs/tts_output_20241108_143022.wav",
  "audio_url": "http://localhost:5000/download/api_outputs/tts_output_20241108_143022.wav",
  "voice_id": "${voiceId}",
  "output_directory": "api_outputs"
}`}</pre>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;