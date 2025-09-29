import os
import uuid
import subprocess
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from pipeline import generate_transcript, generate_notes_from_transcript, process_audio
from stt_engine import transcribe_audio
from werkzeug.utils import secure_filename

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
@app.route("/stream", methods=["POST", "OPTIONS"])
def stream_audio():
    if request.method == "OPTIONS":
        return jsonify({}), 200

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    final = request.form.get("final", "false").lower() == "true"

    # Save incoming .webm chunk
    temp_id = str(uuid.uuid4())
    temp_webm = os.path.join(app.config["UPLOAD_FOLDER"], f"chunk_{temp_id}.webm")
    file.save(temp_webm)

    # Convert webm → wav (16kHz mono PCM)
    temp_wav = os.path.join(app.config["UPLOAD_FOLDER"], f"chunk_{temp_id}.wav")
    result = subprocess.run([
        "ffmpeg", "-y", "-i", temp_webm,
        "-ar", "16000", "-ac", "1", temp_wav
    ], capture_output=True, text=True)
    
    if result.returncode != 0 or not os.path.exists(temp_wav):
        # Clean up
        os.remove(temp_webm)
        return jsonify({"error": "ffmpeg conversion failed", "details": result.stderr}), 500


    # Append wav data to session file
    if not os.path.exists(SESSION_FILE) or final:
        open(SESSION_FILE, "wb").close()

    with open(temp_wav, "rb") as src, open(SESSION_FILE, "ab") as dst:
        dst.write(src.read())

    os.remove(temp_webm)
    os.remove(temp_wav)

    if final:
        try:
            # Step 1: Transcript immediately
            transcript = generate_transcript(SESSION_FILE)
    
            request_id = str(uuid.uuid4())
            app.config[request_id] = {"filepath": SESSION_FILE, "transcript": transcript}
    
            # Clear session for next recording
            open(SESSION_FILE, "wb").close()
            if hasattr(stream_audio, "last_len"):
                del stream_audio.last_len
    
            return jsonify({"request_id": request_id, "transcript": transcript})
        except Exception as e:
            import traceback, sys
            print("=== ERROR in process_audio ===", file=sys.stderr)
            traceback.print_exc()
            print("=== END ERROR ===", file=sys.stderr)
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
