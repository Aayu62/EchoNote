// ==== File Upload Handling ====
const uploadBtn = document.getElementById("uploadBtn");
const fileInput = document.getElementById("fileInput");
let sessionId = null;

// Helper: prepare download buttons
function prepareDownload(buttonId, content, filename) {
  const blob = new Blob([content], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const btn = document.getElementById(buttonId);
  btn.href = url;
  btn.download = filename;
  btn.style.display = "inline-block";
}

uploadBtn.addEventListener("click", async () => {
  const file = fileInput.files[0];
  if (!file) return alert("Please select a file first!");

  const formData = new FormData();
  formData.append("file", file);

  document.getElementById("transcript").textContent = "⏳ Generating transcript...";
  document.getElementById("notes").textContent = "";

  try {
    // Step 1: Upload & get transcript immediately
    const response = await fetch("http://127.0.0.1:5000/process", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();

    if (data.error) {
      alert("Error: " + data.error);
      return;
    }

    // ✅ Transcript shows up immediately
    document.getElementById("transcript").textContent = data.transcript;

    // ✅ Save transcript globally
    window.lastTranscript = data.transcript;
    prepareDownload("downloadTranscriptBtn", data.transcript || "", "transcript.txt");

    // Step 2: Start fetching notes separately
    document.getElementById("notes").textContent = "📝 Generating notes...";
    fetch(`http://127.0.0.1:5000/notes/${data.request_id}`)
      .then((res) => res.json())
      .then((notesData) => {
        if (notesData.error) {
          document.getElementById("notes").textContent = "❌ Error generating notes";
        } else {
          document.getElementById("notes").textContent = notesData.notes;

          // ✅ Save notes globally
          window.lastNotes = notesData.notes;
          prepareDownload("downloadNotesBtn", notesData.notes || "", "notes.txt");
        }
      })
      .catch((err) => {
        document.getElementById("notes").textContent = "❌ Notes fetch failed: " + err;
      });

  } catch (err) {
    alert("Failed to connect to backend: " + err);
  }
});


// ==== Live Recording Handling ====
const recordBtn = document.getElementById("recordBtn");
const stopBtn = document.getElementById("stopBtn");
const liveTranscriptEl = document.getElementById("liveTranscript");
const finalNotesEl = document.getElementById("finalNotes");

let mediaRecorder;
let globalStream;
let recordedChunks = [];
let chunkQueue = [];
let chunkInterval;

recordBtn.addEventListener("click", async () => {
  try {
    sessionId = crypto.randomUUID();           // <-- new: unique session id per recording
    window.currentSessionId = sessionId;
    globalStream = await navigator.mediaDevices.getUserMedia({ audio: true });

    // MIME type fallback
    let options = { mimeType: "audio/webm;codecs=opus" };
    if (!MediaRecorder.isTypeSupported(options.mimeType)) options = { mimeType: "audio/webm" };
    if (!MediaRecorder.isTypeSupported(options.mimeType)) options = { mimeType: "audio/wav" };

    mediaRecorder = new MediaRecorder(globalStream, options);
    recordedChunks = [];
    chunkQueue = [];

    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        recordedChunks.push(event.data);
        chunkQueue.push(event.data);
      }
    };

    mediaRecorder.onstart = () => console.log("Recording started");
    mediaRecorder.onstop = () => console.log("Recording stopped");
    mediaRecorder.onerror = (e) => console.error("Recorder error:", e);

    // ✅ Fire `ondataavailable` every 2s
    mediaRecorder.start(2000);

    // Send queued chunks every 2s
    chunkInterval = setInterval(() => {
      if (chunkQueue.length === 0) return;
      const chunk = chunkQueue.shift();
      const formData = new FormData();
      formData.append("file", chunk, "chunk.webm");
      formData.append("session_id", sessionId);   // <-- send session id
      fetch("http://127.0.0.1:5000/stream", { method: "POST", body: formData })
        .then(res => res.json())
        .then(data => {
          // server will return {"partial": "..."} for non-final chunks
          if (data.partial) {
            // append partial with small spacing
            liveTranscriptEl.textContent += (data.partial + " ");
          }
        })
        .catch(err => console.error("Chunk upload failed:", err));
    }, 2000);

    recordBtn.disabled = true;
    stopBtn.disabled = false;
    liveTranscriptEl.textContent = "🎙️ Recording...\n";
    finalNotesEl.textContent = "";

  } catch (err) {
    alert("Mic access denied or not available: " + err);
  }
});

stopBtn.addEventListener("click", async () => {
  if (!mediaRecorder) return;

  mediaRecorder.stop();
  clearInterval(chunkInterval);
  recordBtn.disabled = false;
  stopBtn.disabled = true;

  const finalBlob = new Blob(recordedChunks, { type: mediaRecorder.mimeType });
  const formData = new FormData();
  formData.append("file", finalBlob, "final.webm");
  formData.append("final", "true");
  formData.append("session_id", sessionId);

  liveTranscriptEl.innerHTML += '\n\n<span class="loading"></span> Finalizing transcript...';
  finalNotesEl.innerHTML = "";

  try {
    const response = await fetch("http://127.0.0.1:5000/stream", { method: "POST", body: formData });
    const data = await response.json();

    if (data.error) {
      alert("Error: " + data.error);
      return;
    }

    // ✅ Show transcript immediately
    liveTranscriptEl.textContent = data.transcript || "No transcript";
    window.lastTranscript = data.transcript;
    prepareDownload("downloadTranscriptBtn", data.transcript || "", "transcript.txt");

    // ✅ Fetch notes separately
    finalNotesEl.textContent = "📝 Generating notes...";
    fetch(`http://127.0.0.1:5000/notes/${data.request_id}`)
      .then(res => res.json())
      .then(notesData => {
        if (notesData.error) {
          finalNotesEl.textContent = "❌ Error generating notes";
        } else {
          finalNotesEl.textContent = notesData.notes;
          window.lastNotes = notesData.notes;
          prepareDownload("downloadNotesBtn", notesData.notes || "", "notes.txt");
        }
      })
      .catch(err => {
        finalNotesEl.textContent = "❌ Notes fetch failed: " + err;
      });

    recordedChunks = [];
    chunkQueue = [];
  } catch (err) {
    alert("Error finishing recording: " + err);
  }
});


// =======================
// Store transcript & notes globally
// =======================
function handleBackendResponse(data) {
  if (data.transcript) {
    window.lastTranscript = data.transcript;
  }
  if (data.notes) {
    window.lastNotes = data.notes;
  }
}
