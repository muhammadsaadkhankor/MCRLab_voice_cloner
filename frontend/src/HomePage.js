import React from 'react';
import { useNavigate } from 'react-router-dom';
import './App.css';

function HomePage() {
  const navigate = useNavigate();

  const goToVoiceCloner = () => {
    navigate('/voice-cloner');
  };

  return (
    <div className="App">
      {/* Header */}
      <div className="header">
        <div className="header-content">
          <div className="header-title">
            <h1>HUMAIN</h1>
            <p className="subtitle">Voice Cloning Studio</p>
          </div>
        </div>
      </div>

      <div className="container">
        {/* Hero Section */}
        <div className="hero-section">
          <h1 className="hero-title">Voice Cloning Technology</h1>
          <p className="hero-description">
            Clone any voice with just 3 seconds of audio
          </p>
        </div>

        {/* Main Option */}
        <div className="options-grid">
          <div className="option-card">
            <div className="option-icon">🎵</div>
            <h3>Voice Cloning Studio</h3>
            <p>Clone any voice with just 3 seconds of audio. Generate speech using predefined voices or create your own voice profile.</p>
            <button className="option-btn" onClick={goToVoiceCloner}>
              Start Voice Cloning
            </button>
          </div>
        </div>

        {/* Features Section */}
        <div className="features-section">
          <h2>Why Choose HUMAIN Voice Cloning?</h2>
          <div className="features-grid">
            <div className="feature-item">
              <div className="feature-icon">⚡</div>
              <h4>Fast Processing</h4>
              <p>15-second audio chunks for optimal quality</p>
            </div>
            <div className="feature-item">
              <div className="feature-icon">🎯</div>
              <h4>High Accuracy</h4>
              <p>Advanced AI models for realistic voice generation</p>
            </div>
            <div className="feature-item">
              <div className="feature-icon">🔒</div>
              <h4>Secure & Private</h4>
              <p>Your voice data stays protected</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default HomePage;