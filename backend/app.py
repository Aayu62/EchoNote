import os
import uuid
import subprocess
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from pipeline import generate_transcript, generate_notes_from_transcript, process_audio
from stt_engine import transcribe_audio
from werkzeug.utils import secure_filename
import shutil
import time

app = Flask(__name__, static_folder="../frontend", static_url_path="/")
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True, methods=["GET", "POST", "OPTIONS"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "data", "recordings")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

SESSION_FILE = os.path.join(app.config["UPLOAD_FOLDER"], "live_session.wav")

# ==== Serve frontend files ====
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:filename>")
def frontend_files(filename):
    return send_from_directory(app.static_folder, filename)

# ==== Live streaming endpoint ====
def ffmpeg_concat_wavs(wav_paths, out_path):
    list_file = out_path + "_inputs.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for p in wav_paths:
            f.write(f"file '{p}'\n")
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", list_file,
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        out_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    os.remove(list_file)
    if result.returncode != 0:
        raise RuntimeError("ffmpeg concat failed: " + result.stderr)
    return out_path
@app.route("/stream", methods=["POST", "OPTIONS"])
def stream_audio():
    if request.method == "OPTIONS":
        return jsonify({}), 200

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    final = request.form.get("final", "false").lower() == "true"
    session_id = request.form.get("session_id") or "default_session"

    # create session-specific folder
    session_dir = os.path.join(app.config["UPLOAD_FOLDER"], session_id)
    os.makedirs(session_dir, exist_ok=True)

    # Save incoming .webm chunk
    temp_uuid = str(uuid.uuid4())
    temp_webm = os.path.join(session_dir, f"chunk_{temp_uuid}.webm")
    file.save(temp_webm)

    # Convert webm → wav (16kHz mono PCM)
    temp_wav = os.path.join(session_dir, f"chunk_{temp_uuid}.wav")
    result = subprocess.run([
        "ffmpeg", "-y", "-i", temp_webm,
        "-ar", "16000", "-ac", "1", temp_wav
    ], capture_output=True, text=True)

    # remove webm immediately
    try:
        os.remove(temp_webm)
    except:
        pass

    if result.returncode != 0 or not os.path.exists(temp_wav):
        return jsonify({"error": "ffmpeg conversion failed", "details": result.stderr}), 500

    # Keep per-session state in app.config
    sess_key = f"stream_{session_id}"
    if sess_key not in app.config:
        app.config[sess_key] = {"chunks": [], "transcript_so_far": ""}

    # Transcribe just this chunk (fast, single-file)
    try:
        chunk_text = transcribe_audio(temp_wav, save_path=None)
    except Exception as e:
        # if stt fails, remove the temp wav and return error
        try:
            os.remove(temp_wav)
        except:
            pass
        return jsonify({"error": "stt_failed", "details": str(e)}), 500

    # Save chunk path for concatenation later
    app.config[sess_key]["chunks"].append(temp_wav)
    # Append to transcript_so_far (simple approach)
    app.config[sess_key]["transcript_so_far"] = (app.config[sess_key]["transcript_so_far"] + " " + chunk_text).strip()

    if not final:
        # For non-final chunks: return the immediate chunk transcription
        return jsonify({"partial": chunk_text})

    # FINAL CHUNK: concatenate and run the full pipeline
    try:
        full_out = os.path.join(session_dir, f"{session_id}_full.wav")
        ffmpeg_concat_wavs(app.config[sess_key]["chunks"], full_out)

        # Option A: run your pipeline/process to produce transcript + notes
        transcript = generate_transcript(full_out)  # saves transcript if pipeline does
        request_id = str(uuid.uuid4())
        app.config[request_id] = {"filepath": full_out, "transcript": transcript}

        # cleanup chunk WAVs (keep final for storage if desired)
        for p in app.config[sess_key]["chunks"]:
            try:
                os.remove(p)
            except:
                pass
        del app.config[sess_key]

        return jsonify({"request_id": request_id, "transcript": transcript})
    except Exception as e:
        return jsonify({"error": "processing_failed", "details": str(e)}), 500

    

# ==== Full file upload endpoint ====
from pipeline import generate_transcript, generate_notes_from_transcript

# File upload: transcript first
@app.route("/process", methods=["POST", "OPTIONS"])
def process_file():
    if request.method == "OPTIONS":
        return jsonify({}), 200

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    # Step 1: Transcript immediately
    transcript = generate_transcript(filepath)

    # Store transcript temporarily in memory (or DB/cache if multi-user)
    request_id = str(uuid.uuid4())
    app.config[request_id] = {"filepath": filepath, "transcript": transcript}

    return jsonify({"request_id": request_id, "transcript": transcript})


# Fetch notes later
@app.route("/notes/<request_id>", methods=["GET"])
def get_notes(request_id):
    if request_id not in app.config:
        return jsonify({"error": "Invalid request ID"}), 404

    info = app.config[request_id]
    transcript = info["transcript"]
    filepath = info["filepath"]

    notes = generate_notes_from_transcript(transcript, filepath)
    return jsonify({"notes": notes})


if __name__ == "__main__":
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.run(debug=True)
