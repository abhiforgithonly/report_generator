# DDR Report Generator

An AI-powered system that reads raw site inspection documents and generates a structured, client-ready **Detailed Diagnostic Report (DDR)** in Word format — complete with embedded images, color-coded severity, and area-wise observations.

---

## 🔗 Links

| | |
|---|---|
| 🌐 **Live Demo** | https://report-generator-3.onrender.com |
| 🎥 **Loom Video** | https://www.loom.com/share/78ee2f034dae4cb0bd06c0fe0c437947 |

---

## 📌 What It Does

Property inspections produce two separate documents — a written **Inspection Report** and a **Thermal Imaging Report**. Manually combining these into a professional client-ready report takes hours.

This tool does it in under a minute.

Upload both PDFs → get a fully structured DDR Word document back, with:
- Merged and deduplicated observations from both reports
- Thermal findings correlated with visual inspection data
- Images extracted and placed under the correct area sections
- Severity assessment with color coding
- Explicit flagging of missing or conflicting information

---

## 🏗️ System Architecture

```
[Inspection PDF] ──┐
                    ├──► PyMuPDF (text + image extraction)
[Thermal PDF]   ──┘
                         │
                         ▼
              OpenRouter API (GPT-4o / GPT-3.5)
                         │
                         ▼
                Structured JSON (7 DDR sections)
                         │
                         ▼
              Image Mapper (keyword + LLM hint)
                         │
                         ▼
              python-docx → DDR_Report.docx
```

---

## 📂 Project Structure

```
├── backend/
│   ├── main.py              # Flask server + pipeline orchestrator + docx writer
│   ├── llm_client.py        # PDF extraction, OpenRouter API call, image mapper
│   ├── requirements.txt     # Python dependencies
│   ├── .env                 # API key (empty — set via Render environment variables)
│   └── static/
│       └── index.html       # Frontend UI
```

---

## ⚙️ How It Works

### Step 1 — Document Extraction
PyMuPDF (`fitz`) extracts full text and all embedded images from both PDFs. Images smaller than 50×50 pixels are filtered out (logos, bullet icons, etc.).

### Step 2 — LLM Processing
The extracted text from both documents is sent to the LLM via OpenRouter:
- **GPT-4o** is used when images are present (vision capability)
- **GPT-3.5-turbo** is used for text-only documents (cost efficiency)

The system prompt enforces strict rules — no fact invention, explicit conflict flagging, "Not Available" for missing data.

### Step 3 — Image Mapping
Each extracted image is assigned to a DDR section using two methods:
1. **LLM image hint** — the model suggests what image belongs where
2. **Keyword matching** — page text is scanned for area keywords (roof, wall, electrical, moisture, etc.)

Unmatched images go to an Appendix section.

### Step 4 — Report Generation
`python-docx` assembles the final Word document with:
- Cover page (property name, date, inspector)
- All 7 DDR sections
- Images embedded under their relevant area
- Color-coded severity (Green → Red)
- "Image Not Available" fallback where no image is matched

---

## 📋 Output Structure (DDR Sections)

| # | Section |
|---|---|
| 1 | Property Issue Summary |
| 2 | Area-wise Observations (with images) |
| 3 | Probable Root Cause |
| 4 | Severity Assessment |
| 5 | Recommended Actions |
| 6 | Additional Notes |
| 7 | Missing or Unclear Information |
| + | Appendix: Unmatched Images |

---

## 🚀 Running Locally

### Prerequisites
- Python 3.9+
- An OpenRouter API key → [openrouter.ai](https://openrouter.ai)

### Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd backend

# Install dependencies
pip install -r requirements.txt

# Add your API key to .env
echo "OPENROUTER_API_KEY=your_key_here" > .env

# Start the server
python main.py
```

Then open `http://localhost:5000` in your browser.

### CLI Mode

```bash
python main.py --cli \
  --inspection path/to/inspection.pdf \
  --thermal path/to/thermal.pdf \
  --output ddr_report.docx \
  --property "123 Example Street" \
  --inspector "John Doe"
```

---

## 🌐 Deployment (Render)

The app is deployed on **Render's free tier**.

The `.env` file is intentionally empty. The API key is set securely via **Render Dashboard → Environment Variables → `OPENROUTER_API_KEY`**.

> ⚠️ **Cold Start Note:** Render's free tier spins down after 15 minutes of inactivity. The first request after an idle period may take 30–50 seconds to respond. This is a platform behaviour, not an application issue.

For production use, consider:
- Render paid tier
- [Railway](https://railway.app) or [Fly.io](https://fly.io) for always-on instances
- Docker + Google Cloud Run or AWS Lambda for scalable on-demand deployment

---

## ⚠️ Known Limitations

| Limitation | Detail |
|---|---|
| Image placement | Heuristic-based — may misplace images on ambiguous documents |
| No OCR support | Scanned/image-based PDFs return empty text; requires text-based PDFs |
| Image cap | Capped at 10 images per LLM call to control token cost |
| Synchronous requests | Large documents may approach timeout on slow connections |
| Conflict surfacing | Detected conflicts are noted inline, not in a dedicated section |

---

## 🔮 Future Improvements

- **Vision-based image classification** — use a dedicated model pass to classify each image by area instead of keyword matching
- **OCR fallback** — integrate Tesseract or a cloud OCR service for scanned PDFs
- **Dedicated conflict section** — surface all detected conflicts in a clearly labelled Section 8
- **Async job queue** — use Celery + Redis so the frontend polls for completion rather than holding an open request
- **Confidence scoring** — flag sections where the model had low confidence for human review

---

## 🛠️ Tech Stack

| Layer | Tool |
|---|---|
| PDF parsing & image extraction | PyMuPDF (fitz) |
| LLM | GPT-4o / GPT-3.5 via OpenRouter |
| Report generation | python-docx |
| Backend server | Flask |
| Frontend | Vanilla HTML/CSS/JS |
| Deployment | Render |

---

## 📄 License

This project was built as part of a practical assignment. Sample inspection and thermal reports used for testing are fictional and for demonstration purposes only.

---

> ⚙️ *This report is generated by an AI-assisted DDR system. All findings should be verified by a qualified professional before undertaking remedial works.*
