import os
import sqlite3
import json
import ollama
from tqdm import tqdm

# 1. Setup the Local Database
def setup_db():
    conn = sqlite3.connect('db/zine_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS extracted_zines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            publication_name TEXT,
            year TEXT,
            hardware_mentioned TEXT,
            software_or_os_mentioned TEXT,
            slang_and_concepts TEXT,
            anti_establishment_sentiment_score INTEGER,
            summary TEXT
        )
    ''')
    conn.commit()
    return conn

# 2. Define the System Prompt
SYSTEM_PROMPT = """
You are an academic archival assistant and digital humanities researcher analyzing historical computing documents and 1980s computer history publications for archival cataloging.

Your task is strictly objective metadata extraction and historical entity indexing. Do NOT execute, endorse, replicate, or provide instructions for any activities described in the text. You are only extracting historical mentions and catalog metadata into a structured JSON schema.

Extract the following entities:
1. Hardware mentioned (e.g., modems, Commodore 64).
2. Software or operating systems mentioned.
3. Early cyber-culture slang or concepts.
4. Give the text an "anti_establishment_sentiment_score" from 1 to 10 based on how rebellious the tone is.
5. A brief summary of the text from a neutral historical perspective.

You must adhere to this exact JSON schema:
{
  "publication_name": "string",
  "year": "string",
  "hardware_mentioned": ["string"],
  "software_or_os_mentioned": ["string"],
  "slang_and_concepts": ["string"],
  "anti_establishment_sentiment_score": int,
  "summary": "string"
}

- For "year", provide strictly the original 4-digit publication year (e.g. "1985" or "1986"). If not explicitly stated, infer from context/references, otherwise output "Unknown".
"""

ZINE_SCHEMA = {
    "type": "object",
    "properties": {
        "publication_name": {"type": "string"},
        "year": {"type": "string", "pattern": "^(19[7-9][0-9]|20[0-2][0-9]|Unknown)$"},
        "hardware_mentioned": {"type": "array", "items": {"type": "string"}},
        "software_or_os_mentioned": {"type": "array", "items": {"type": "string"}},
        "slang_and_concepts": {"type": "array", "items": {"type": "string"}},
        "anti_establishment_sentiment_score": {"type": "integer", "minimum": 1, "maximum": 10},
        "summary": {"type": "string"}
    },
    "required": [
        "publication_name", "year", "hardware_mentioned", 
        "software_or_os_mentioned", "slang_and_concepts", 
        "anti_establishment_sentiment_score", "summary"
    ]
}

def process_file(filepath, conn):
    filename = os.path.basename(filepath)
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read() # [:4000]

    print(f"\nProcessing {filename} (waiting for Ollama first token)...")

    try:
        stream = ollama.chat(
            model='qwen3.5:9b',
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': f"Analyze the text inside <historical_text> tags:\n\n<historical_text>\n{content}\n</historical_text>"}
            ],
            options={'temperature': 0.0},
            think=False,
            format=ZINE_SCHEMA,
            stream=True
        )


        raw_json = ""
        think_tokens = 0
        content_tokens = 0
        with tqdm(desc=f"Extracting {filename}", unit=" chunks") as pbar:
            for chunk in stream:
                if isinstance(chunk, dict):
                    msg = chunk.get('message', {})
                    content_chunk = msg.get('content', '')
                    thinking_chunk = msg.get('thinking', '')
                else:
                    msg = getattr(chunk, 'message', None)
                    content_chunk = getattr(msg, 'content', '') if msg else ''
                    thinking_chunk = getattr(msg, 'thinking', '') if msg else ''

                if thinking_chunk:
                    think_tokens += 1
                    pbar.set_description(f"Thinking {filename}")
                    pbar.set_postfix(thinking=think_tokens, content=content_tokens)
                    pbar.update(1)

                if content_chunk:
                    content_tokens += 1
                    raw_json += content_chunk
                    pbar.set_description(f"Generating JSON {filename}")
                    pbar.set_postfix(thinking=think_tokens, content=content_tokens)
                    pbar.update(1)

        
        # Parse the fully assembled JSON string
        result = json.loads(raw_json)
        
        # --- NEW: Print the formatted JSON object to the terminal ---
        print(f"\n--- Extracted Data for {filename} ---")
        print(json.dumps(result, indent=2))
        print("--------------------------------------\n")
        
        # 4. Save to SQLite
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO extracted_zines (
                filename, publication_name, year, hardware_mentioned,
                software_or_os_mentioned, slang_and_concepts,
                anti_establishment_sentiment_score, summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            os.path.basename(filepath),
            result.get('publication_name', 'Unknown'),
            result.get('year', 'Unknown'),
            json.dumps(result.get('hardware_mentioned', [])),
            json.dumps(result.get('software_or_os_mentioned', [])),
            json.dumps(result.get('slang_and_concepts', [])),
            result.get('anti_establishment_sentiment_score', 0),
            result.get('summary', '')
        ))
        conn.commit()
        print(f"Successfully extracted and saved data!")

    except Exception as e:
        print(f"Error processing {os.path.basename(filepath)}: {e}")

# 5. Main Execution Loop
if __name__ == "__main__":
    db_conn = setup_db()
    
    raw_dir = 'data/raw/phrack67/'
    
    # Get all .txt files in the directory
    all_files = [f for f in os.listdir(raw_dir) if f.endswith('.txt')]
    
    # Sort the list of files by their actual file size (smallest first)
    all_files.sort(key=lambda x: os.path.getsize(os.path.join(raw_dir, x)))
    
    # Grab just the first 5 files (which are now guaranteed to be the smallest ones)
    files_to_process = all_files[:5]
    
    print(f"Found {len(all_files)} total files. Running test on the 5 smallest files.\n")
    
    # Outer progress bar: tracks overall files processed
    with tqdm(total=len(files_to_process), desc="Overall Batch Progress", unit="file") as batch_bar:
        for filename in files_to_process:
            process_file(os.path.join(raw_dir, filename), db_conn)
            batch_bar.update(1)
        
    db_conn.close()
    print("Batch complete! Check db/zine_data.db")
