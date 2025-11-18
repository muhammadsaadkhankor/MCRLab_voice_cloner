import sqlite3
import os
from datetime import datetime

class VoiceDatabase:
    def __init__(self, db_path="voices.db"):
        self.db_path = db_path
        self.init_database()
        self.setup_predefined_voices()
    
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS voices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                audio_path TEXT NOT NULL,
                text_path TEXT NOT NULL,
                is_predefined BOOLEAN DEFAULT 0,
                voice_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_key TEXT UNIQUE NOT NULL,
                voice_ids TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Check if voice_id column exists, if not add it
        cursor.execute("PRAGMA table_info(voices)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'voice_id' not in columns:
            cursor.execute('ALTER TABLE voices ADD COLUMN voice_id TEXT')
        
        conn.commit()
        conn.close()
    
    def setup_predefined_voices(self):
        predefined_voices = [
            {"name": "Saad", "audio_path": "samples/saad.wav", "text_path": "samples/saad.txt"},
            {"name": "Professor Abed", "audio_path": "samples/professor_abed.wav", "text_path": "samples/professor_abed.txt"},
            {"name": "Tariq Amin", "audio_path": "samples/tariq_amin.wav", "text_path": "samples/tariq_amin.txt"}
        ]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for voice in predefined_voices:
            cursor.execute('''
                INSERT OR IGNORE INTO voices (name, audio_path, text_path, is_predefined)
                VALUES (?, ?, ?, 1)
            ''', (voice["name"], voice["audio_path"], voice["text_path"]))
        
        conn.commit()
        conn.close()
    
    def get_all_voices(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, audio_path, text_path, is_predefined, voice_id, created_at
            FROM voices ORDER BY is_predefined DESC, name
        ''')
        
        voices = []
        for row in cursor.fetchall():
            voices.append({
                "id": row[0],
                "name": row[1],
                "audio_path": row[2],
                "text_path": row[3],
                "is_predefined": bool(row[4]),
                "voice_id": row[5],
                "created_at": row[6]
            })
        
        conn.close()
        return voices
    
    def get_voice_by_name(self, name):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, audio_path, text_path, is_predefined, voice_id, created_at
            FROM voices WHERE name = ?
        ''', (name,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "id": row[0],
                "name": row[1],
                "audio_path": row[2],
                "text_path": row[3],
                "is_predefined": bool(row[4]),
                "voice_id": row[5],
                "created_at": row[6]
            }
        return None
    
    def add_voice(self, name, audio_path, text_path, is_predefined=False, voice_id=None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO voices (name, audio_path, text_path, is_predefined, voice_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, audio_path, text_path, is_predefined, voice_id))
        
        db_voice_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return db_voice_id
    
    def save_api_key(self, api_key, voice_ids):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        voice_ids_str = ','.join(voice_ids)
        cursor.execute('''
            INSERT OR REPLACE INTO api_keys (api_key, voice_ids)
            VALUES (?, ?)
        ''', (api_key, voice_ids_str))
        
        conn.commit()
        conn.close()
    
    def get_all_api_keys(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT api_key, voice_ids FROM api_keys')
        api_data = {}
        
        for row in cursor.fetchall():
            api_key = row[0]
            voice_ids = row[1].split(',') if row[1] else []
            api_data[api_key] = voice_ids
        
        conn.close()
        return api_data