import sqlite3
import os
from datetime import datetime
import random
import string

class VoiceDatabase:
    def __init__(self, db_path="voices.db"):
        self.db_path = db_path
        self.init_database()
        self.migrate_database()
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def migrate_database(self):
        """Handle database migrations"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if voice_id column exists
        cursor.execute("PRAGMA table_info(voices)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'voice_id' not in columns:
            cursor.execute('ALTER TABLE voices ADD COLUMN voice_id TEXT')
            conn.commit()
        
        conn.close()
    
    def generate_voice_id(self):
        """Generate a unique 12-character alphanumeric voice ID"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    
    def setup_predefined_voices(self):
        predefined_voices = [
            {"name": "Saad", "audio_path": "samples/saad.wav", "text_path": "samples/saad.txt"},
            {"name": "Professor Abed", "audio_path": "samples/professor_abed.wav", "text_path": "samples/professor_abed.txt"},
            {"name": "Christine", "audio_path": "samples/christine.wav", "text_path": "samples/christine.txt"}
        ]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for voice in predefined_voices:
            # Check if voice already exists
            cursor.execute('SELECT id, voice_id FROM voices WHERE name = ?', (voice["name"],))
            existing = cursor.fetchone()
            
            if existing:
                # Voice exists, check if it has voice_id
                if not existing[1]:  # No voice_id
                    voice_id = self.generate_voice_id()
                    cursor.execute('UPDATE voices SET voice_id = ? WHERE name = ?', (voice_id, voice["name"]))
            else:
                # Voice doesn't exist, create it
                voice_id = self.generate_voice_id()
                cursor.execute('''
                    INSERT INTO voices (name, audio_path, text_path, voice_id, is_predefined)
                    VALUES (?, ?, ?, ?, 1)
                ''', (voice["name"], voice["audio_path"], voice["text_path"], voice_id))
        
        conn.commit()
        conn.close()
    
    def get_all_voices(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, audio_path, text_path, voice_id, is_predefined, created_at
            FROM voices ORDER BY is_predefined DESC, name
        ''')
        
        voices = []
        for row in cursor.fetchall():
            voices.append({
                "id": row[0],
                "name": row[1],
                "audio_path": row[2],
                "text_path": row[3],
                "voice_id": row[4],
                "is_predefined": bool(row[5]),
                "created_at": row[6]
            })
        
        conn.close()
        return voices
    
    def get_voice_by_name(self, name):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, audio_path, text_path, voice_id, is_predefined, created_at
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
                "voice_id": row[4],
                "is_predefined": bool(row[5]),
                "created_at": row[6]
            }
        return None
    
    def add_voice(self, name, audio_path, text_path, is_predefined=False):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        voice_id = self.generate_voice_id()
        cursor.execute('''
            INSERT INTO voices (name, audio_path, text_path, voice_id, is_predefined)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, audio_path, text_path, voice_id, is_predefined))
        
        conn.commit()
        conn.close()
        return voice_id
    
    def get_voice_by_id(self, voice_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, audio_path, text_path, voice_id, is_predefined, created_at
            FROM voices WHERE id = ?
        ''', (voice_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "id": row[0],
                "name": row[1],
                "audio_path": row[2],
                "text_path": row[3],
                "voice_id": row[4],
                "is_predefined": bool(row[5]),
                "created_at": row[6]
            }
        return None
    
    def delete_voice(self, voice_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM voices WHERE id = ?', (voice_id,))
        conn.commit()
        conn.close()
    
    def get_voice_by_voice_id(self, voice_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, audio_path, text_path, voice_id, is_predefined, created_at
            FROM voices WHERE voice_id = ?
        ''', (voice_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "id": row[0],
                "name": row[1],
                "audio_path": row[2],
                "text_path": row[3],
                "voice_id": row[4],
                "is_predefined": bool(row[5]),
                "created_at": row[6]
            }
        return None