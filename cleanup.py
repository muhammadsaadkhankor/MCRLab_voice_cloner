#!/usr/bin/env python3
import os
import glob

def cleanup_temp_files():
    """Clean up all temporary audio files"""
    patterns = [
        "ai_response_*.mp3",
        "greeting_*.mp3", 
        "question_*.mp3",
        "first_question_*.mp3",
        "response_*.wav",
        "response_*.mp3",
        "temp_*.wav",
        "api_output_*.wav"
    ]
    
    for pattern in patterns:
        files = glob.glob(pattern)
        for file in files:
            try:
                os.remove(file)
                print(f"Removed: {file}")
            except:
                pass

if __name__ == "__main__":
    cleanup_temp_files()
    print("Cleanup completed!")