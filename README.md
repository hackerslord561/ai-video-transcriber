# AI Video Transcriber

## Setup Instructions (IntelliJ IDEA)

1. **System Requirement:** Ensure you have `ffmpeg` installed on your computer and added to your system PATH.
2. **Open Project:** Open this folder in IntelliJ IDEA.
3. **Setup Interpreter:** - Go to `File > Project Structure > SDKs`.
    - Add a new Python SDK (Virtual Environment) and point it to this project folder.
4. **Install Dependencies:**
    - Open the embedded Terminal in IntelliJ (`Alt + F12` on Windows/Linux or `Option + F12` on Mac).
    - Run: `pip install -r requirements.txt`
5. **Run the App:**
    - In the same terminal, run: `streamlit run app.py`
    - Your browser will automatically open to `http://localhost:8501`.