#!/usr/bin/env python3
"""M0 Adapter & Extraction Evaluator for cv-extractor on Golden Dataset 15 Core CVs."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

CV_EXTRACTOR_SRC = Path("/srv/hermes-control/services/cv-extractor/src")
if str(CV_EXTRACTOR_SRC) not in sys.path:
    sys.path.insert(0, str(CV_EXTRACTOR_SRC))

from cv_extractor.application.config import PipelineConfig, OcrConfig, LlmConfig
from cv_extractor.bootstrap import build_service

MONTHS_MAP = {
    "jan": "01", "januari": "01", "january": "01",
    "feb": "02", "februari": "02", "pebruari": "02", "february": "02",
    "mar": "03", "maret": "03", "march": "03",
    "apr": "04", "april": "04",
    "mei": "05", "may": "05",
    "jun": "06", "juni": "06", "june": "06",
    "jul": "07", "juli": "07", "july": "07",
    "agu": "08", "agt": "08", "agus": "08", "agustus": "08", "aug": "08", "august": "08",
    "sep": "09", "sept": "09", "september": "09",
    "okt": "10", "oktober": "10", "oct": "10", "october": "10",
    "nov": "11", "nopember": "11", "november": "11",
    "des": "12", "desember": "12", "dec": "12", "december": "12",
}

PRESENT_SET = {"sekarang", "saat ini", "kini", "present", "now", "current", "currently", "to date"}
MONTHS_REGEX_STR = r"(?:jan(?:uari|uary)?|feb(?:ruari|ruary)?|mar(?:et|ch)?|apr(?:il)?|mei|may|jun(?:i|e)?|jul(?:i|y)?|agu(?:stus)?|aug(?:ust)?|sep(?:t(?:ember)?)?|okt(?:ober)?|oct(?:ober)?|nov(?:ember)?|des(?:ember)?|dec(?:ember)?)"

RANGE_REGEX = re.compile(
    rf"({MONTHS_REGEX_STR}\s+\d{{4}}|\d{{1,2}}/\d{{4}}|\b\d{{4}}\b)\s*(?:[-–—=]|s/d|sd|to|sampai|hingga|until)\s*({MONTHS_REGEX_STR}(?:\s+\d{{4}})?|\d{{1,2}}/\d{{4}}|\b\d{{4}}\b|sekarang|present|saat ini|current|now)",
    re.IGNORECASE
)

def norm_single_date(s: str, is_end: bool = False, ref_year: str = "") -> str:
    s = s.strip().lower()
    if any(p in s for p in PRESENT_SET):
        return "present"
    
    # MM/YYYY
    m = re.match(r"(\d{1,2})/(\d{4})", s)
    if m:
        return f"{m.group(2)}-{int(m.group(1)):02d}"
    
    # Month Name YYYY
    m = re.match(rf"({MONTHS_REGEX_STR})\s+(\d{{4}})", s)
    if m:
        mname = m.group(1)
        year = m.group(2)
        mcode = MONTHS_MAP.get(mname[:3], "01")
        return f"{year}-{mcode}"
        
    # Month name without year (e.g. AGUSTUS 2022 – FEBRUARI) -> next year if end date month < start date month
    m = re.match(rf"^({MONTHS_REGEX_STR})$", s)
    if m and ref_year:
        mname = m.group(1)
        mcode = MONTHS_MAP.get(mname[:3], "01")
        # If end month is smaller than start month (e.g. Feb vs Aug), it rolled over into next year
        year_num = int(ref_year)
        if is_end:
            year_num += 1
        return f"{year_num}-{mcode}"
        
    # Year only
    m = re.match(r"^\d{4}$", s)
    if m:
        y = m.group(0)
        return f"{y}-07" if not is_end else f"{y}-06"
        
    return s

def extract_exp_blocks(text: str) -> list[dict]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    entries = []
    
    date_lines = []
    for idx, l in enumerate(lines):
        m = RANGE_REGEX.search(l)
        if m:
            date_lines.append((idx, m.group(1), m.group(2), m.start(), m.end()))
            
    for i, (idx, raw_start, raw_end, m_start, m_end) in enumerate(date_lines):
        # determine ref year from start
        ref_y = ""
        m_y = re.search(r"\b(\d{4})\b", raw_start)
        if m_y:
            ref_y = m_y.group(1)
            
        start_date = norm_single_date(raw_start, is_end=False, ref_year=ref_y)
        end_date = norm_single_date(raw_end, is_end=True, ref_year=ref_y)
        
        curr_line = lines[idx]
        pre_text = curr_line[:m_start].strip()
        
        title = ""
        org = ""
        
        if pre_text:
            parts = re.split(r"[—|]", pre_text)
            if len(parts) >= 2:
                title = parts[0].strip()
                org = parts[1].strip().split(",")[0].strip()
            else:
                title = pre_text.strip()
        elif idx > 0:
            prev_line = lines[idx - 1]
            parts = re.split(r"[—|]", prev_line)
            if len(parts) >= 2:
                title = parts[0].strip()
                org = parts[1].strip().split(",")[0].strip()
            else:
                title = prev_line.strip()
                if idx > 1:
                    org = lines[idx - 2].strip()
                    
        next_idx = date_lines[i + 1][0] if i + 1 < len(date_lines) else len(lines)
        block_text = " ".join(lines[idx:next_idx]).lower()
        if idx > 0 and not pre_text:
            block_text = lines[idx - 1].lower() + " " + block_text
            
        emp_type = "full_time"
        if "intern" in block_text or "magang" in block_text or "internship" in block_text:
            emp_type = "internship"
        elif "freelance" in block_text or "lepas" in block_text:
            emp_type = "freelance"
        elif "kontrak" in block_text or "contract" in block_text:
            emp_type = "contract"
        elif "part-time" in block_text or "paruh waktu" in block_text:
            emp_type = "part_time"
            
        if title:
            title = re.split(r"[—|]", title)[0].strip()
            entries.append({
                "title": title,
                "organization": org,
                "start": start_date,
                "end": end_date,
                "employment_type": emp_type
            })
            
    return entries

def parse_skills(section_text: str) -> list[str]:
    items = re.split(r"[,•\n\r]+", section_text)
    cleaned = []
    for it in items:
        s = it.strip().strip("-*").strip()
        if s and len(s) < 50:
            cleaned.append(s)
    return cleaned

def parse_certifications(ce_text: str, ed_text: str) -> list[str]:
    combined = ce_text
    # Check if education text contains hidden certification section (e.g. OCR noise '~ Sertifikasi')
    if "sertifikasi" in ed_text.lower() or "certification" in ed_text.lower():
        parts = re.split(r"~?\s*(?:sertifikasi|certifications?)\b", ed_text, flags=re.IGNORECASE)
        if len(parts) > 1:
            combined += "\n" + parts[1]
            
    # Normalize wrapped lines
    lines = [l.strip().lstrip("-•*~ ").strip() for l in combined.splitlines() if l.strip()]
    merged = []
    curr = ""
    for l in lines:
        if curr and (l.startswith("Developer") or l.startswith("Engineer") or l.startswith("(") or l.startswith("—") or l.startswith("-")):
            curr += " " + l
        else:
            if curr:
                merged.append(curr)
            curr = l
    if curr:
        merged.append(curr)
        
    return [l for l in merged if len(l) > 3 and not l.lower().startswith("keahlian") and not l.lower().startswith("skills")]

def parse_education(section_text: str) -> list[dict]:
    levels = []
    t = section_text.lower()
    if re.search(r"\bs1\b|sarjana|bachelor", t):
        levels.append({"level": "S1"})
    if re.search(r"\bs2\b|magister|master", t):
        levels.append({"level": "S2"})
    if re.search(r"\bd3\b|diploma 3|diploma iii", t):
        levels.append({"level": "D3"})
    if re.search(r"\bd4\b|diploma 4|diploma iv", t):
        levels.append({"level": "D4"})
    if re.search(r"\bsmk\b", t):
        levels.append({"level": "SMK"})
    if re.search(r"\bsma\b", t):
        levels.append({"level": "SMA"})
    if not levels and re.search(r"universitas|institut|politeknik|college", t):
        levels.append({"level": "S1"})
    return levels

def run_extraction():
    core_dir = Path("/srv/hermes-control/services/cv-screening/docs/spec/golden_dataset/cvs/core")
    files = sorted(list(core_dir.glob("*.pdf")) + list(core_dir.glob("*.docx")))
    
    service = build_service(PipelineConfig(ocr=OcrConfig(), llm=LlmConfig(enabled=False)))
    
    output = {"files": {}}
    for f in files:
        res = service.extract(f.read_bytes(), f.name).to_dict()
        sec_map = {}
        for s in res.get("sections", []):
            lbl = s["label"]
            sec_map.setdefault(lbl, []).append(s.get("text", ""))
            
        exp_text = "\n".join(sec_map.get("experience", []))
        sk_text = "\n".join(sec_map.get("skills", []))
        ce_text = "\n".join(sec_map.get("certifications", []))
        ed_text = "\n".join(sec_map.get("education", []))
        
        output["files"][f.name] = {
            "experiences": extract_exp_blocks(exp_text),
            "education": parse_education(ed_text),
            "certifications": parse_certifications(ce_text, ed_text),
            "skills": parse_skills(sk_text)
        }
        
    out_path = Path("/srv/hermes-control/services/cv-screening/scripts/pred_extraction.json")
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"Generated {out_path} for {len(output['files'])} files.")

if __name__ == "__main__":
    run_extraction()
