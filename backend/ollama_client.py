import requests
import json
import os

def generate_notes(transcript_text, save_path=None):
    url = "http://localhost:11434/api/generate"
    headers = {"Content-Type": "application/json"}
    payload = {
        "model": "mistral",
        "prompt": f"""
            You are an assistant that creates class notes for students.
            Convert the following transcript into **well-structured study notes** with:
            
            - A short title
            - Main headings & subheadings
            - Bullet points for key details
            - Highlight important terms with CAPITAL letters
            
        Transcript:
        {transcript_text}
        """,
    }
    

    response = requests.post(url, headers=headers, data=json.dumps(payload), stream=True)

    notes = ""
    for line in response.iter_lines():
        if line:
            data = json.loads(line.decode("utf-8"))
            if "response" in data:
                notes += data["response"]

    if save_path:
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(notes)

    return notes

if __name__ == "__main__":
    transcript = open("../data/transcripts/polymath_transcript.txt").read()
    notes_file = "../data/notes/sample_notes.txt"
    print(generate_notes(transcript, notes_file))
