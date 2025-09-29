import os
from stt_engine import transcribe_audio
from ollama_client import generate_notes
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def process_audio(audio_file):
    transcript_file = os.path.join(BASE_DIR, "data", "transcripts", f"{os.path.basename(audio_file)}.txt")
    notes_file = os.path.join(BASE_DIR, "data", "notes", f"{os.path.basename(audio_file)}_notes.txt")

    # Step 1: Speech-to-Text
    transcript = transcribe_audio(audio_file, transcript_file)

    # Step 2: Notes from Ollama
    notes = generate_notes(transcript, notes_file)

    return transcript, notes

def generate_transcript(audio_file):
    transcript_file = os.path.join(BASE_DIR, "data", "transcripts", f"{os.path.basename(audio_file)}.txt")
    transcript = transcribe_audio(audio_file, transcript_file)
    return transcript

def generate_notes_from_transcript(transcript, audio_file):
    notes_file = os.path.join(BASE_DIR, "data", "notes", f"{os.path.basename(audio_file)}_notes.txt")
    notes = generate_notes(transcript, notes_file)
    return notes


if __name__ == "__main__":
    audio_path = os.path.join(BASE_DIR, "data", "recordings", "Sample2.wav")
    transcript, notes = process_audio(audio_path)
    print("=== Transcript Preview ===")
    print(transcript[:200], "...")
    print("\n=== Notes Preview ===")
    print(notes[:200], "...")
