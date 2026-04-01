from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google import genai
import pdfplumber
from docx import Document
import json
import asyncio
import os
import io
from typing import List
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="ResumeIQ API")

# ── CORS (allows your frontend to talk to this backend) ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Gemini setup ──
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)


# ────────────────────────────────────────────
# HELPERS
# ────────────────────────────────────────────

def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages).strip()
    except Exception:
        return ""

def extract_text_from_docx(file_bytes: bytes) -> str:
    try:
        doc = Document(io.BytesIO(file_bytes))
        return "\n".join([para.text for para in doc.paragraphs]).strip()
    except Exception:
        return ""


def extract_text(filename: str, file_bytes: bytes) -> str:
    ext = filename.lower().split(".")[-1]
    if ext == "pdf":
        return extract_text_from_pdf(file_bytes)
    elif ext in ("docx", "doc"):
        return extract_text_from_docx(file_bytes)
    return ""


async def score_batch(jd_text: str, batch: list) -> list:
    resumes_block = ""
    for i, r in enumerate(batch):
        resumes_block += f"\n---RESUME {i+1} | FILE: {r['filename']}---\n{r['text'][:3000]}\n"

    prompt = f"""
You are an expert HR recruiter. Score each resume against the job description below.

JOB DESCRIPTION:
{jd_text[:2000]}

RESUMES TO SCORE:
{resumes_block}

For EACH resume return a JSON array. Each item must have:
- "filename": the filename exactly as given
- "candidate_name": extract from resume (or use filename if not found)
- "experience_summary": 1 short line about their background
- "score": integer 0-100 based on fit
- "matched_skills": list of up to 5 matched skills
- "missing_skills": list of up to 3 missing skills
- "reason": 2-sentence explanation of the score
- "match_level": one of "Strong", "Good", "Partial", "Weak"

Return ONLY a valid JSON array. No markdown, no explanation, just the array.
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        return [
            {
                "filename": r["filename"],
                "candidate_name": r["filename"],
                "experience_summary": "Could not parse",
                "score": 0,
                "matched_skills": [],
                "missing_skills": [],
                "reason": f"Scoring failed: {str(e)}",
                "match_level": "Weak",
            }
            for r in batch
        ]


# ────────────────────────────────────────────
# ROUTES
# ────────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "ResumeIQ API is running. Go to /docs to test."}


@app.post("/analyze")
async def analyze(
    jd_text: str = Form(default=""),
    jd_file: UploadFile = File(default=None),
    resumes: List[UploadFile] = File(...),
):
    # ── Step 1: Get JD text ──
    if jd_file and jd_file.filename:
        jd_bytes = await jd_file.read()
        job_description = extract_text(jd_file.filename, jd_bytes)
    elif jd_text.strip():
        job_description = jd_text.strip()
    else:
        raise HTTPException(status_code=400, detail="Please provide a job description.")

    if not job_description:
        raise HTTPException(status_code=400, detail="Could not read the job description file.")

    # ── Step 2: Extract text from all resumes ──
    parsed_resumes = []
    skipped = []

    for resume_file in resumes:
        file_bytes = await resume_file.read()
        text = extract_text(resume_file.filename, file_bytes)
        if not text:
            skipped.append(resume_file.filename)
            continue
        parsed_resumes.append({"filename": resume_file.filename, "text": text})

    if not parsed_resumes:
        raise HTTPException(status_code=400, detail="No readable resumes found.")

    # ── Step 3: Score in batches of 10 ──
    BATCH_SIZE = 10
    all_results = []

    for i in range(0, len(parsed_resumes), BATCH_SIZE):
        batch = parsed_resumes[i: i + BATCH_SIZE]
        batch_results = await score_batch(job_description, batch)
        all_results.extend(batch_results)
        if i + BATCH_SIZE < len(parsed_resumes):
            await asyncio.sleep(4)

    # ── Step 4: Sort by score descending ──
    all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
    for idx, r in enumerate(all_results):
        r["rank"] = idx + 1

    # ── Step 5: Summary stats ──
    strong  = sum(1 for r in all_results if r.get("score", 0) >= 80)
    good    = sum(1 for r in all_results if 55 <= r.get("score", 0) < 80)
    partial = sum(1 for r in all_results if 35 <= r.get("score", 0) < 55)
    weak    = sum(1 for r in all_results if r.get("score", 0) < 35)

    return {
        "total": len(all_results),
        "skipped": skipped,
        "stats": {
            "strong": strong,
            "good": good,
            "partial": partial,
            "weak": weak,
        },
        "results": all_results,
    }
