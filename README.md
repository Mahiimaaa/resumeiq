# ResumeIQ 🧠
An AI-powered resume screening web app that scores and ranks candidates against a job description using Google Gemini AI.

## What it does
- HR person uploads a job description + multiple resumes (PDF or DOCX)
- AI reads and scores each resume from 0–100
- Results are ranked with matched skills, missing skills, and a reason for each score
- Results can be exported as CSV

## Tech Stack
- **Frontend:** HTML, Tailwind CSS, Vanilla JavaScript
- **Backend:** FastAPI (Python)
- **AI:** Google Gemini API (gemini-2.0-flash)
- **PDF Parsing:** pdfplumber
- **DOCX Parsing:** python-docx
- **Server:** uvicorn

## Setup Instructions

### 1. Clone the repo
```bash
git clone https://github.com/Mahiimaaa/resumeiq.git
cd resumeiq
```

### 2. Create a virtual environment
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Add your Gemini API key
Create a `.env` file in the root folder: 
