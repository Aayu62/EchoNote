import whisper
import os

MODEL_NAME = os.environ.get("WHISPER_MODEL", "small")
model = whisper.load_model(MODEL_NAME)

def transcribe_audio(audio_path, save_path=None):
    """
    Transcribe audio file.
    - If save_path is given: saves transcript and returns it.
    - If not: just returns transcript (used for live/partial updates).
    """
    # for faster realtime behavior, you can pass additional whisper args later
    result = model.transcribe(audio_path)
    transcript = result.get("text", "").strip()

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
