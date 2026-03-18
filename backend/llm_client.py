"""
llm_client.py
Handles PDF extraction (text + images) and OpenRouter API calls.
GPT-3.5 for text-only docs, GPT-4o when images are present.
"""

import os
import json
import base64
import requests
import fitz  # PyMuPDF
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_TEXT_ONLY = "openai/gpt-3.5-turbo"
MODEL_WITH_IMAGES = "openai/gpt-4o"


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class PageImage:
    page_number: int
    image_bytes: bytes
    base64_str: str
    extension: str
    width: int
    height: int


@dataclass
class ExtractedDocument:
    filename: str
    full_text: str
    page_texts: List[str]
    images: List[PageImage] = field(default_factory=list)


# ── Extraction ─────────────────────────────────────────────────────────────────

def extract_document(pdf_path: str) -> ExtractedDocument:
    """Extract text and images from a PDF using PyMuPDF."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(pdf_path)
    page_texts = []
    images = []

    for page_num, page in enumerate(doc):
        page_texts.append(page.get_text("text").strip())

        for img_info in page.get_images(full=True):
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
                w, h = base_image["width"], base_image["height"]
                if w < 50 or h < 50:
                    continue  # skip tiny icons/bullets
                img_bytes = base_image["image"]
                images.append(PageImage(
                    page_number=page_num + 1,
                    image_bytes=img_bytes,
                    base64_str=base64.b64encode(img_bytes).decode("utf-8"),
                    extension=base_image["ext"],
                    width=w,
                    height=h,
                ))
            except Exception as e:
                print(f"[WARN] Skipping image on page {page_num+1}: {e}")

    doc.close()
    return ExtractedDocument(
        filename=os.path.basename(pdf_path),
        full_text="\n\n--- PAGE BREAK ---\n\n".join(page_texts),
        page_texts=page_texts,
        images=images,
    )


# ── Prompt ─────────────────────────────────────────────────────────────────────

DDR_SYSTEM_PROMPT = """You are an expert building inspector and technical report writer.
You will be given raw inspection data from two sources:
1. A site Inspection Report (observations, defects, notes)
2. A Thermal Report (temperature readings, thermal findings)

Generate a professional DDR (Detailed Diagnostic Report) that is clear and client-friendly.

CRITICAL RULES:
- Do NOT invent facts not present in the documents
- If information conflicts between the two reports, explicitly mention the conflict
- If information is missing, write exactly: "Not Available"
- Merge related/duplicate observations — do not repeat the same point twice
- Use simple language suitable for a property owner

OUTPUT FORMAT — respond ONLY with a valid JSON object, no markdown fences:
{
  "property_issue_summary": "...",
  "area_wise_observations": [
    {
      "area": "Area name",
      "observations": ["observation 1", "observation 2"],
      "image_hint": "brief description of what image belongs here, or null"
    }
  ],
  "probable_root_cause": "...",
  "severity_assessment": {
    "level": "Low | Medium | High | Critical",
    "reasoning": "..."
  },
  "recommended_actions": ["action 1", "action 2"],
  "additional_notes": "...",
  "missing_or_unclear_information": ["item 1"]
}"""


# ── OpenRouter API call ────────────────────────────────────────────────────────

def call_openrouter(inspection_doc: ExtractedDocument, thermal_doc: ExtractedDocument) -> dict:
    """Call OpenRouter — GPT-3.5 for text-only, GPT-4o when images are found."""
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not set in .env")

    all_images = inspection_doc.images + thermal_doc.images
    use_vision = len(all_images) > 0
    model = MODEL_WITH_IMAGES if use_vision else MODEL_TEXT_ONLY

    print(f"[INFO] Model: {model} | Images: {len(all_images)}")

    text_block = f"""=== INSPECTION REPORT ===
{inspection_doc.full_text}

=== THERMAL REPORT ===
{thermal_doc.full_text}"""

    if use_vision:
        content = [{"type": "text", "text": text_block + "\n\nImages from the documents are attached below."}]
        for img in all_images[:10]:  # cap at 10 to control cost
            media_type = "image/jpeg" if img.extension in ("jpg", "jpeg") else f"image/{img.extension}"
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{media_type};base64,{img.base64_str}",
                    "detail": "low",
                },
            })
        messages = [{"role": "user", "content": content}]
    else:
        messages = [{"role": "user", "content": text_block}]

    response = requests.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://ddr-generator.local",
            "X-Title": "DDR Report Generator",
        },
        json={
            "model": model,
            "messages": [{"role": "system", "content": DDR_SYSTEM_PROMPT}, *messages],
            "max_tokens": 4000,
            "temperature": 0.2,
        },
        timeout=120,
    )

    if response.status_code != 200:
        raise RuntimeError(f"OpenRouter error {response.status_code}: {response.text}")

    raw = response.json()["choices"][0]["message"]["content"].strip()

    # Strip accidental markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}\n\nRaw:\n{raw}")


# ── Image mapper ───────────────────────────────────────────────────────────────

AREA_KEYWORDS = {
    "roof":       ["roof", "ceiling", "terrace", "slab", "overhead"],
    "wall":       ["wall", "plaster", "paint", "crack", "facade"],
    "floor":      ["floor", "tile", "ground", "base"],
    "bathroom":   ["bathroom", "toilet", "washroom", "drain", "pipe"],
    "kitchen":    ["kitchen", "sink", "counter"],
    "electrical": ["electrical", "wiring", "circuit", "switch", "panel"],
    "window":     ["window", "frame", "glass", "shutter"],
    "door":       ["door", "hinge", "lock"],
    "foundation": ["foundation", "basement", "footing", "plinth"],
    "moisture":   ["moisture", "damp", "seepage", "leakage", "water", "thermal"],
}


def assign_images_to_sections(
    area_observations: list,
    all_images: List[PageImage],
    page_texts_inspection: List[str],
    page_texts_thermal: List[str],
) -> dict:
    """Map images to DDR sections via LLM hint + page keyword heuristics."""
    assigned = {area["area"]: [] for area in area_observations}
    assigned["__unmatched__"] = []
    all_page_texts = page_texts_inspection + page_texts_thermal

    for img in all_images:
        matched = False

        # Priority 1: match via LLM-provided image_hint
        for area_obs in area_observations:
            hint = (area_obs.get("image_hint") or "").lower()
            area_lower = area_obs["area"].lower()
            keywords = AREA_KEYWORDS.get(area_lower, [area_lower])
            if hint and any(kw in hint for kw in keywords):
                assigned[area_obs["area"]].append(img)
                matched = True
                break

        if matched:
            continue

        # Priority 2: match via page text keywords
        page_idx = img.page_number - 1
        if page_idx < len(all_page_texts):
            page_text = all_page_texts[page_idx].lower()
            for area_obs in area_observations:
                area_lower = area_obs["area"].lower()
                keywords = AREA_KEYWORDS.get(area_lower, [area_lower])
                if any(kw in page_text for kw in keywords):
                    assigned[area_obs["area"]].append(img)
                    matched = True
                    break

        if not matched:
            assigned["__unmatched__"].append(img)

    return assigned
