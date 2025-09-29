import whisper
import os

# Load model once globally (avoid reloading on every call)
model = whisper.load_model("base")  # try "small" or "medium" for better accuracy

def transcribe_audio(audio_path, save_path=None):
    """
    Transcribe audio file.
    - If save_path is given: saves transcript and returns it.
    - If not: just returns transcript (used for live/partial updates).
    """
    result = model.transcribe(audio_path)
    transcript = result["text"]

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(transcript)

    return transcript

if __name__ == "__main__":
    audio = "../data/recordings/Sample2.wav"
    transcript_file = "../data/transcripts/sample.txt"
    text = transcribe_audio(audio, transcript_file)
    print("Transcript:", text[:200], "...")
