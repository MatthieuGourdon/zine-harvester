import os
import sqlite3
import json
import ollama
from tqdm import tqdm

# 1. Setup the Local Database
def setup_db():
    conn = sqlite3.connect('db/zine_data.db')
    cursor = conn.cursor()
    
    # We replaced 'anti_establishment_sentiment_score' with 'source_collection'
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_collection TEXT,
            filename TEXT,
            publication_name TEXT,
            year TEXT,
            summary TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER,
            category TEXT,
            value TEXT,
            FOREIGN KEY(document_id) REFERENCES documents(id)
        )
    ''')
    conn.commit()
    return conn

# 2. Define the System Prompt
SYSTEM_PROMPT = """
You are an automated historical data extraction API. 
Analyze the raw text and extract entities strictly as a JSON object.

Based on the text's theme (Hacking, Tabletop RPGs, or Sci-Fi), populate the relevant entity arrays. Leave irrelevant arrays empty.

Entity Categories:
1. hardware_mentioned (e.g., modems, Commodore 64)
2. software_or_os (e.g., Unix, RSTS)
3. cyber_slang (e.g., phreaking, sysop)
4. rpg_systems_and_classes (e.g., AD&D, dwarf, rogue, GURPS)
5. sci_fi_authors_and_books (e.g., William Gibson, Neuromancer)
6. sci_fi_tropes (e.g., cyberspace, megacorps, faster-than-light)

You must adhere to this exact JSON schema:
{
  "publication_name": "string",
  "year": "string",
  "hardware_mentioned": ["string"],
  "software_or_os": ["string"],
  "cyber_slang": ["string"],
  "rpg_systems_and_classes": ["string"],
  "sci_fi_authors_and_books": ["string"],
  "sci_fi_tropes": ["string"],
  "summary": "string"
}

- For "publication_name", provide strictly one single lowercase word (e.g. "phrack" or "unknown").
- For "year", provide strictly the original 4-digit publication year (e.g. "1985" or "1986"). If not explicitly stated, infer from context/references, otherwise output "Unknown".
"""

ZINE_SCHEMA = {
    "type": "object",
    "properties": {
        "publication_name": {"type": "string", "pattern": "^[a-z0-9_-]+$"},
        "year": {"type": "string", "pattern": "^(19[7-9][0-9]|20[0-2][0-9]|Unknown)$"},
        "hardware_mentioned": {"type": "array", "items": {"type": "string"}},
        "software_or_os": {"type": "array", "items": {"type": "string"}},
        "cyber_slang": {"type": "array", "items": {"type": "string"}},
        "rpg_systems_and_classes": {"type": "array", "items": {"type": "string"}},
        "sci_fi_authors_and_books": {"type": "array", "items": {"type": "string"}},
        "sci_fi_tropes": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"}
    },
    "required": [
        "publication_name", "year", "hardware_mentioned", 
        "software_or_os", "cyber_slang", "rpg_systems_and_classes",
        "sci_fi_authors_and_books", "sci_fi_tropes", "summary"
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
        
        # 4. Save to SQLite Relational Tables
        cursor = conn.cursor()
        
        # We can extract the folder name from the filepath to know which collection it belongs to
        source_collection = os.path.basename(os.path.dirname(filepath))
        
        cursor.execute('''
            INSERT INTO documents (
                source_collection, filename, publication_name, year, summary
            ) VALUES (?, ?, ?, ?, ?)
        ''', (
            source_collection,
            os.path.basename(filepath),
            result.get('publication_name', 'Unknown'),
            result.get('year', 'Unknown'),
            result.get('summary', '')
        ))
        
        doc_id = cursor.lastrowid
        
        def insert_entities(entity_list, category_name):
            if not isinstance(entity_list, list): return
            for item in entity_list:
                cursor.execute('''
                    INSERT INTO entities (document_id, category, value) 
                    VALUES (?, ?, ?)
                ''', (doc_id, category_name, str(item)))

        # Dynamically map the JSON arrays to database categories
        insert_entities(result.get('hardware_mentioned', []), 'hardware')
        insert_entities(result.get('software_or_os', []), 'software')
        insert_entities(result.get('cyber_slang', []), 'cyber_slang')
        insert_entities(result.get('rpg_systems_and_classes', []), 'rpg_elements')
        insert_entities(result.get('sci_fi_authors_and_books', []), 'sci_fi_references')
        insert_entities(result.get('sci_fi_tropes', []), 'sci_fi_tropes')
        
        conn.commit()
        print(f"Successfully extracted and saved relational data!")

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
