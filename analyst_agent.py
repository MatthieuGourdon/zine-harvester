import sqlite3
import json
import ollama

def get_database_context():
    # Connect to the DB and format the rows as dictionaries
    conn = sqlite3.connect('db/zine_data.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Grab all records
    cursor.execute("SELECT publication_name, year, hardware_mentioned, software_or_os_mentioned, slang_and_concepts, summary FROM extracted_zines")
    rows = cursor.fetchall()
    
    data = [dict(row) for row in rows]
    conn.close()
    
    return json.dumps(data, indent=2)

def main():
    print("Loading historical database...")
    db_context = get_database_context()
    record_count = len(json.loads(db_context))
    print(f"✅ Loaded {record_count} zine records into Analyst Agent memory.\n")
    
    print("Type your questions about the cyber-culture data (or 'exit' to quit).")
    print("-" * 50)
    
    while True:
        question = input("\nQuery > ")
        if question.lower() in ['exit', 'quit']:
            break
            
        system_prompt = f"""
        You are an expert digital humanities researcher and historian of 1980s/1990s cyber-culture. 
        You have been provided with a structured database export of early hacker zines.
        Answer the user's question based strictly on the DATABASE EXPORT provided below. 
        If the answer cannot be found in the data, state clearly that the data does not contain that information. 
        Do not hallucinate or invent historical facts outside of this export.
        
        DATABASE EXPORT:
        {db_context}
        """
        
        # We disable 'think' here so it answers immediately like a fast chat bot
        stream = ollama.chat(
            model='qwen3.5:9b',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': question}
            ],
            think=False,
            stream=True
        )
        
        print("\nAnalyst: ", end="", flush=True)
        for chunk in stream:
            # Safely extract the content chunk based on your previous fix
            if isinstance(chunk, dict):
                content_chunk = chunk.get('message', {}).get('content', '')
            else:
                msg = getattr(chunk, 'message', None)
                content_chunk = getattr(msg, 'content', '') if msg else ''
                
            print(content_chunk, end="", flush=True)
        print("\n")

if __name__ == "__main__":
    main()
