import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';

function ApiPage() {
  const [apiName, setApiName] = useState('');
  const [selectedVoiceId, setSelectedVoiceId] = useState('');
  const [createdApi, setCreatedApi] = useState(null);
  const [voices, setVoices] = useState([]);
  const [customVoices, setCustomVoices] = useState([]);
  const [copiedField, setCopiedField] = useState('');
  const [loading, setLoading] = useState(false);
  
  // Custom voice creation states
  const [isRecording, setIsRecording] = useState(false);
  const [customVoiceName, setCustomVoiceName] = useState('');
  const [transcript, setTranscript] = useState('');
  const [refData, setRefData] = useState(null);
  
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const fileInputRef = useRef(null);

  useEffect(() => {
    fetchVoices();
    fetchCustomVoices();
  }, []);

  const fetchVoices = async () => {
    try {
      const response = await axios.get('http://localhost:4000/get_voices');
      console.log('Fetched voices:', response.data.voices);
      const predefinedVoices = response.data.voices.filter(v => v.is_predefined);
      console.log('Predefined voices:', predefinedVoices);
      setVoices(predefinedVoices);
    } catch (error) {
      console.error('Error fetching voices:', error);
    }
  };

  const fetchCustomVoices = async () => {
    try {
      const response = await axios.get('http://localhost:4000/get_custom_voices');
      setCustomVoices(response.data.voices || []);
    } catch (error) {
      console.error('Error fetching custom voices:', error);
    }
  };

  const createAPI = async () => {
    if (!apiName) {
      alert('Please enter a name for your API key');
      return;
    }

    setLoading(true);
    try {
      const response = await axios.post('http://localhost:4000/create_api_key', {
        api_name: apiName
      });
      
      setCreatedApi(response.data);
    } catch (error) {
      alert('Error creating API key: ' + (error.response?.data?.error || error.message));
    }
    setLoading(false);
  };

  const copyToClipboard = (text, field) => {
    navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(''), 2000);
  };

  // Custom voice recording functions
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      chunksRef.current = [];

      mediaRecorderRef.current.ondataavailable = (event) => {
        chunksRef.current.push(event.data);
      };

      mediaRecorderRef.current.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/wav' });
        await uploadCustomVoice(blob);
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

  const uploadCustomVoice = async (audioBlob, filename = 'custom_voice.wav') => {
    setLoading(true);
    const formData = new FormData();
    formData.append('audio', audioBlob, filename);

    try {
      const response = await axios.post('http://localhost:4000/upload_reference', formData);
      setRefData(response.data);
      setTranscript(response.data.transcript);
    } catch (error) {
      alert('Error uploading voice: ' + error.message);
    }
    setLoading(false);
  };

  const handleFileUpload = (event) => {
    const file = event.target.files[0];
    if (file) {
      uploadCustomVoice(file, file.name);
    }
  };

  const saveCustomVoice = async () => {
    if (!customVoiceName || !refData) {
      alert('Please provide voice name and record/upload audio');
      return;
    }

    setLoading(true);
    try {
      const response = await axios.post('http://localhost:4000/save_custom_voice', {
        voice_name: customVoiceName,
        audio_path: refData.audio_path,
        text_path: refData.text_path,
        transcript: transcript
      });
      
      alert('Custom voice saved successfully!');
      setCustomVoiceName('');
      setRefData(null);
      setTranscript('');
      fetchCustomVoices();
    } catch (error) {
      alert('Error saving custom voice: ' + (error.response?.data?.error || error.message));
    }
    setLoading(false);
  };

  return (
    <div className="App">
      {/* Header */}
      <div className="header">
        <div className="header-content">
          <div className="header-title">
            <h1>API MANAGEMENT</h1>
            <p className="subtitle">Create and manage your voice APIs</p>
          </div>
        </div>
      </div>

      <div className="container">
        {/* Create API Key Section */}
        <div className="section">
          <div className="section-header">
            <h2>🔑 CREATE API KEY</h2>
            <p className="section-description">Generate your personal API key for voice cloning access</p>
          </div>

          {!createdApi ? (
            <div className="api-creation-form">
              <div className="form-group">
                <label>Name your API Key:</label>
                <input
                  type="text"
                  value={apiName}
                  onChange={(e) => setApiName(e.target.value)}
                  placeholder="Enter a name for your API key (e.g., My Voice App)"
                  className="text-input"
                />
              </div>

              <button 
                className="create-api-btn"
                onClick={createAPI}
                disabled={!apiName || loading}
              >
                {loading ? '🔄 Creating...' : '🚀 Create API Key'}
              </button>
            </div>
          ) : (
            <div className="api-created">
              <h3>🎉 API Key Created Successfully!</h3>
              <div className="api-details">
                <div className="api-field">
                  <label>API Key Name:</label>
                  <div className="input-group">
                    <input type="text" value={createdApi.api_name} readOnly />
                  </div>
                </div>
                <div className="api-field">
                  <label>API Key:</label>
                  <div className="input-group">
                    <input type="text" value={createdApi.api_key} readOnly />
                    <button 
                      className="copy-btn"
                      onClick={() => copyToClipboard(createdApi.api_key, 'createdApiKey')}
                    >
                      {copiedField === 'createdApiKey' ? '✓ Copied' : '📋 Copy'}
                    </button>
                  </div>
                </div>
              </div>
              <p className="api-note">⚠️ Save this API key securely. You won't be able to see it again!</p>
              <button 
                className="create-another-btn"
                onClick={() => {
                  setCreatedApi(null);
                  setApiName('');
                }}
              >
                Create Another API Key
              </button>
            </div>
          )}
        </div>

        {/* Custom Voices Section */}
        <div className="section">
          <div className="section-header">
            <h2>🎤 CUSTOM VOICES</h2>
            <p className="section-description">Create your own voice IDs by recording or uploading audio</p>
          </div>

          <div className="custom-voice-creation">
            <div className="form-group">
              <label>Voice Name:</label>
              <input
                type="text"
                value={customVoiceName}
                onChange={(e) => setCustomVoiceName(e.target.value)}
                placeholder="Enter name for your custom voice"
                className="text-input"
              />
            </div>

            <div className="voice-options">
              <button 
                className={`voice-btn ${isRecording ? 'recording' : ''}`}
                onClick={isRecording ? stopRecording : startRecording}
                disabled={loading}
              >
                <span className="btn-icon">🎤</span>
                {isRecording ? 'Stop Recording' : 'Record Voice'}
              </button>
              
              <span className="or-text">OR</span>
              
              <button 
                className="voice-btn"
                onClick={() => fileInputRef.current.click()}
                disabled={loading || isRecording}
              >
                <span className="btn-icon">📤</span>
                Upload Audio
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
                  onClick={saveCustomVoice}
                  className="submit-btn"
                  disabled={!customVoiceName || loading}
                >
                  {loading ? '💾 Saving...' : '💾 Save Custom Voice'}
                </button>
              </div>
            )}
          </div>

          {/* Custom Voices List */}
          {customVoices.length > 0 && (
            <div className="custom-voices-list">
              <h3>Your Custom Voices ({customVoices.length})</h3>
              <div className="voices-grid">
                {customVoices.map((voice) => (
                  <div key={voice.id} className="voice-card custom">
                    <div className="voice-info">
                      <h4>{voice.name}</h4>
                      <span className="voice-status custom">Custom</span>
                    </div>
                    <div className="voice-id-section">
                      <label>Voice ID:</label>
                      <div className="input-group">
                        <code className="voice-id">{voice.voice_id}</code>
                        <button 
                          className="copy-btn small"
                          onClick={() => copyToClipboard(voice.voice_id, `list_${voice.id}`)}
                        >
                          {copiedField === `list_${voice.id}` ? '✓' : '📋'}
                        </button>
                      </div>
                    </div>
                    <div className="voice-ready">
                      <span className="ready-icon">✓</span>
                      Ready for API use
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Usage Examples */}
        <div className="section">
          <div className="section-header">
            <h2>📖 USAGE EXAMPLES</h2>
            <p className="section-description">How to use the voice cloning API</p>
          </div>

          <div className="usage-examples">
            <div className="usage-example">
              <h4>Basic API Call:</h4>
              <pre className="code-block">
{`curl -X POST http://localhost:4000/api/tts \\
  -H "Authorization: Bearer ${createdApi?.api_key || 'sk_your_api_key_here'}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "voice_id": "voice_professor_abed",
    "text": "Hello, this is my cloned voice!"
  }'`}
              </pre>
            </div>

            <div className="usage-example">
              <h4>Save to Downloads:</h4>
              <pre className="code-block">
{`curl -X POST http://localhost:4000/api/tts \\
  -H "Authorization: Bearer ${createdApi?.api_key || 'sk_your_api_key_here'}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "voice_id": "voice_christine",
    "text": "This will be saved to Downloads!",
    "output_path": "$HOME/Downloads/my_voice.wav"
  }'`}
              </pre>
            </div>

            <div className="usage-example">
              <h4>List Available Voices:</h4>
              <pre className="code-block">
{`curl -X GET http://localhost:4000/api/voices \\
  -H "Authorization: Bearer ${createdApi?.api_key || 'sk_your_api_key_here'}"`}
              </pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ApiPage;