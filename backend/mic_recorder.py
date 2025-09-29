import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import os
from pipeline import process_audio, BASE_DIR

def record_audio(filename="mic_input.wav", duration=10, samplerate=16000, device=None):
    print(f"🎙️ Recording for {duration} seconds...")

    if device is not None:
        sd.default.device = device
        info = sd.query_devices(device)
        max_channels = info['max_input_channels']
        print(f"ℹ️ Using device: {info['name']} | Max input channels: {max_channels}")
    else:
        # Default device
        info = sd.query_devices(sd.default.device[0])
        max_channels = info['max_input_channels']
        print(f"ℹ️ Using default device: {info['name']} | Max input channels: {max_channels}")

    if max_channels < 1:
        raise RuntimeError("❌ Selected device has no input channels!")

    # Pick min(1, max_channels) → if only stereo available, record 2 channels
    channels = 1 if max_channels >= 1 else max_channels
    recording = sd.rec(int(duration * samplerate),
                       samplerate=samplerate,
                       channels=channels,
                       dtype='int16')
    sd.wait()

    file_path = os.path.join(BASE_DIR, "data", "recordings", filename)
    wav.write(file_path, samplerate, recording)
    print(f"✅ Audio saved to {file_path}")
    return file_path

if __name__ == "__main__":
    audio_path = record_audio("live_test.wav", duration=8, device=1)

    transcript, notes = process_audio(audio_path)

    print("\n=== Transcript ===")
    print(transcript[:300], "...\n")
    print("=== Notes ===")
    print(notes[:300], "...\n")
