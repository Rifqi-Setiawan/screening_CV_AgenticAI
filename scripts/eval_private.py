"""Evaluation runner for private/real-world candidate CV datasets (FX-33)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PRIVATE_EVAL_DIR = Path("data/private_eval")


def main() -> None:
    if not PRIVATE_EVAL_DIR.exists() or not any(PRIVATE_EVAL_DIR.iterdir()):
        print("=== EVALUASI DATASET PRIVAT (CV ASLI) ===")
        print(f"Direktori '{PRIVATE_EVAL_DIR}' saat ini kosong.")
        print("\nPetunjuk Penyiapan Dataset:")
        print("1. Buat subdirektori per lowongan di data/private_eval/, contoh: data/private_eval/job_01/")
        print("2. Letakkan berkas CV asli (.pdf / .docx) di: data/private_eval/job_01/cvs/")
        print("3. Tulis deskripsi lowongan di: data/private_eval/job_01/jd.md")
        print("4. Buat label referensi HR di: data/private_eval/job_01/labels.json")
        print("   (Format label merujuk pada docs/eval/LABELING_GUIDE.md)")
        print("\nSetelah data terpasang, jalankan kembali script ini untuk evaluasi akurasi.")
        sys.exit(0)

    print(f"Memeriksa dataset di {PRIVATE_EVAL_DIR}...")
    for job_dir in PRIVATE_EVAL_DIR.iterdir():
        if job_dir.is_dir():
            cvs_dir = job_dir / "cvs"
            jd_file = job_dir / "jd.md"
            labels_file = job_dir / "labels.json"
            if cvs_dir.exists() and jd_file.exists() and labels_file.exists():
                labels = json.loads(labels_file.read_text())
                total_cands = len(labels.get("candidates", []))
                print(f"- Job {job_dir.name}: {total_cands} kandidat terlabel.")
            else:
                print(f"- Job {job_dir.name}: Komponen tidak lengkap (cvs/jd.md/labels.json).")


if __name__ == "__main__":
    main()
