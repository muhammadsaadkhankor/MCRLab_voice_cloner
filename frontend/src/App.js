import React, { useState, useRef, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import axios from 'axios';
import HomePage from './HomePage';
import ApiPage from './ApiPage';
import './App.css';

function VoiceClonerPage() {
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
  const [voices, setVoices] = useState([]);
  const [selectedVoice, setSelectedVoice] = useState(null);
  const [voiceInputText, setVoiceInputText] = useState('');
  const [voiceOutputAudio, setVoiceOutputAudio] = useState(null);
  
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
    setSelectedVoice(null); // Clear predefined voice selection
    const formData = new FormData();
    formData.append('audio', audioBlob, filename);

    try {
      const response = await axios.post('http://localhost:4000/upload_reference', formData);
      setRefData({...response.data, submitted: false});
      setTranscript(response.data.transcript);
    } catch (error) {
      alert('Error uploading reference: ' + error.message);
    }
    setLoading(false);
  };

  const submitReference = () => {
    setRefData({...refData, submitted: true});
  };

  const createAPI = async () => {
    if (!refData) {
      alert('Please upload/record a voice first');
      return;
    }
    
    setLoading(true);
    try {
      const response = await axios.post('http://localhost:4000/create_voice_api', {
        audio_path: refData.audio_path,
        text_path: refData.text_path
      });
      
      setVoiceId(response.data.voice_id);
      setApiKey(response.data.api_key);
      setShowApiPanel(true);
    } catch (error) {
      const errorMsg = error.response?.data?.error || error.message;
      alert('Error creating API: ' + errorMsg);
    }
    setLoading(false);
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
      const response = await axios.post('http://localhost:4000/generate_speech', {
        input_text: inputText,
        ref_audio_path: refData.audio_path,
        ref_text_path: refData.text_path
      });
      
      setOutputAudio(`http://localhost:4000/download/${response.data.output_path}?t=${Date.now()}`);
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

  useEffect(() => {
    fetchVoices();
    createPredefinedAPIs();
  }, []);

  const fetchVoices = async () => {
    try {
      const response = await axios.get('http://localhost:4000/get_voices');
      setVoices(response.data.voices);
    } catch (error) {
      console.error('Error fetching voices:', error);
    }
  };

  const createPredefinedAPIs = async () => {
    try {
      const response = await axios.post('http://localhost:4000/create_predefined_apis');
      console.log('Predefined APIs created:', response.data);
      // Set the master API key for display
      setApiKey(response.data.master_api_key);
    } catch (error) {
      console.error('Error creating predefined APIs:', error);
    }
  };



  const selectVoice = (voice) => {
    setSelectedVoice(voice);
    setVoiceInputText('');
    setVoiceOutputAudio(null);
    // Clear custom voice data when selecting predefined voice
    setRefData(null);
    setTranscript('');
    setInputText('');
    setOutputAudio(null);
  };

  const generateVoiceSpeech = async () => {
    if (!selectedVoice || !voiceInputText) return;
    
    setLoading(true);
    try {
      const response = await axios.post('http://localhost:4000/generate_speech_with_voice', {
        voice_name: selectedVoice.name,
        input_text: voiceInputText
      });
      
      setVoiceOutputAudio(`http://localhost:4000/download/${response.data.output_path}?t=${Date.now()}`);
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
          <div className="header-buttons">
            <Link to="/api" className="api-btn">
              Create API
            </Link>
          </div>
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
            {voices.map((voice) => {
              const voiceId = `voice_${voice.name.toLowerCase().replace(/\s+/g, '_')}`;
              return (
                <div 
                  key={voice.id} 
                  className={`voice-card ${selectedVoice?.id === voice.id ? 'selected' : ''} ${!voice.audio_exists ? 'missing-audio' : ''}`}
                  onClick={() => voice.audio_exists && selectVoice(voice)}
                >
                  <div className="voice-info">
                    <h3>{voice.name}</h3>
                    <span className={`voice-status ${voice.is_predefined ? 'predefined' : 'custom'}`}>
                      {voice.is_predefined ? 'Predefined' : 'Custom'}
                    </span>
                  </div>
                  
                  {voice.audio_exists && (
                    <div className="voice-id-display-section">
                      <label>Voice ID:</label>
                      <div className="voice-id-container">
                        <code className="voice-id-text">{voiceId}</code>
                        <button 
                          className="copy-btn mini"
                          onClick={(e) => {
                            e.stopPropagation();
                            copyToClipboard(voiceId, `voice_${voice.id}`);
                          }}
                        >
                          {copiedField === `voice_${voice.id}` ? '✓' : '📋'}
                        </button>
                      </div>
                    </div>
                  )}
                  
                  {!voice.audio_exists && voice.is_predefined && (
                    <div className="missing-audio-notice">
                      <p>Audio file not found</p>
                      <p className="file-path">Expected: {voice.audio_path}</p>
                    </div>
                  )}
                  
                  {voice.audio_exists && (
                    <div className="voice-ready">
                      <span className="ready-icon">✓</span>
                      Ready to use
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

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
              {voiceInputText.length} characters · {voiceInputText.split(' ').length} words · Text over 40 words will be split into 15-second chunks
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
              {inputText.length} characters · {inputText.split(' ').length} words · Text over 40 words will be split into 15-second chunks
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
        
        {/* API Management Panel */}
        {showApiPanel && (
          <div className="section api-section">
            <div className="api-header">
              <h2>🔑 API MANAGEMENT</h2>
              <button className="close-btn" onClick={() => setShowApiPanel(false)}>✕</button>
            </div>
            
            <div className="api-tabs">
              <div className="tab-content">
                <div className="api-master-key">
                  <h3>Master API Key</h3>
                  <div className="input-group">
                    <input type="text" value="mcr_master_api_key_2024" readOnly />
                    <button 
                      className="copy-btn"
                      onClick={() => copyToClipboard('mcr_master_api_key_2024', 'masterKey')}
                    >
                      {copiedField === 'masterKey' ? '✓ Copied' : '📋 Copy'}
                    </button>
                  </div>
                  <p className="api-note">Use this key to access all voice IDs below</p>
                </div>

                <div className="encoded-voices">
                  <h3>📚 Available Encoded Voices ({voices.filter(v => v.audio_exists).length})</h3>
                  <div className="voices-list">
                    {voices.filter(v => v.audio_exists).map((voice) => {
                      const voiceId = `voice_${voice.name.toLowerCase().replace(/\s+/g, '_')}`;
                      return (
                        <div key={voice.id} className="voice-api-card">
                          <div className="voice-details">
                            <h4>{voice.name}</h4>
                            <span className={`voice-type ${voice.is_predefined ? 'predefined' : 'custom'}`}>
                              {voice.is_predefined ? '🏢 Predefined' : '👤 Custom'}
                            </span>
                          </div>
                          <div className="voice-id-section">
                            <label>Voice ID:</label>
                            <div className="input-group">
                              <code className="voice-id">{voiceId}</code>
                              <button 
                                className="copy-btn small"
                                onClick={() => copyToClipboard(voiceId, `voice_${voice.id}`)}
                              >
                                {copiedField === `voice_${voice.id}` ? '✓' : '📋'}
                              </button>
                            </div>
                          </div>
                          <div className="voice-actions">
                            <button 
                              className="test-btn"
                              onClick={() => {
                                setSelectedVoice(voice);
                                setVoiceInputText('Hello, this is a test of my voice!');
                              }}
                            >
                              🎤 Test Voice
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div className="create-custom-voice">
                  <h3>➕ Create New Voice ID</h3>
                  <div className="custom-voice-form">
                    {!refData ? (
                      <div className="upload-prompt">
                        <p>To create a custom voice ID, you need to:</p>
                        <ol>
                          <li>📤 Upload audio file (3-15 seconds, clear speech)</li>
                          <li>📝 Provide transcript (auto-generated or manual)</li>
                          <li>🔧 Encode voice for API usage</li>
                        </ol>
                        <p className="note">Use the "STEP 1: PROVIDE YOUR VOICE" section above to get started.</p>
                      </div>
                    ) : (
                      <div className="voice-ready">
                        <div className="ready-indicator">
                          <span className="status-icon">✅</span>
                          <div>
                            <h4>Voice Sample Ready</h4>
                            <p>Transcript: "{transcript.substring(0, 50)}..."</p>
                          </div>
                        </div>
                        <button 
                          className="create-voice-btn"
                          onClick={createAPI}
                          disabled={loading}
                        >
                          {loading ? '🔄 Creating...' : '🚀 Create Voice ID'}
                        </button>
                        {voiceId && (
                          <div className="new-voice-created">
                            <h4>🎉 New Voice ID Created!</h4>
                            <div className="input-group">
                              <code>{voiceId}</code>
                              <button onClick={() => copyToClipboard(voiceId, 'newVoice')}>📋</button>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
                
                <div className="api-usage">
                  <h3>📖 Usage Examples</h3>
                  
                  <div className="usage-example">
                    <h4>Basic Usage (saves in project):</h4>
                    <pre className="code-block">
{`curl -X POST http://localhost:5000/api/tts \\
  -H "Authorization: Bearer mcr_master_api_key_2024" \\
  -H "Content-Type: application/json" \\
  -d '{
    "voice_id": "voice_professor_abed",
    "text": "Hello, this is my cloned voice!"
  }'`}
                    </pre>
                  </div>

                  <div className="usage-example">
                    <h4>Save to Downloads folder:</h4>
                    <pre className="code-block">
{`curl -X POST http://localhost:5000/api/tts \\
  -H "Authorization: Bearer mcr_master_api_key_2024" \\
  -H "Content-Type: application/json" \\
  -d '{
    "voice_id": "voice_christine",
    "text": "This will be saved to Downloads!",
    "output_path": "$HOME/Downloads/my_voice.mp3"
  }'`}
                    </pre>
                  </div>

                  <div className="usage-example">
                    <h4>List all available voices:</h4>
                    <pre className="code-block">
{`curl -X GET http://localhost:5000/api/voices \\
  -H "Authorization: Bearer mcr_master_api_key_2024"`}
                    </pre>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/voice-cloner" element={<VoiceClonerPage />} />
        <Route path="/api" element={<ApiPage />} />
      </Routes>
    </Router>
  );
}

export { App };