#!/usr/bin/env python3
"""Benchmark 3 embedding models on VPS CPU:
1. paraphrase-multilingual-MiniLM-L12-v2 (384d)
2. microsoft/harrier-oss-v1-270m (640d)
3. Qwen/Qwen3-Embedding-0.6B (1024d)

Measures:
- Latency & throughput for 100 CV text chunks
- Retrieval accuracy: whether correct evidence chunks rank in Top-3 for JD-01 criteria queries
"""
from __future__ import annotations

import time
from pathlib import Path
import numpy as np
from sentence_transformers import SentenceTransformer

# 100 representative CV bullet points and snippets from 15 core CVs
CHUNKS = [
    # Python & Frameworks
    "Mendesain arsitektur microservices berbasis Python (FastAPI) untuk sistem pelacakan paket.",
    "Membangun REST API pembayaran dengan Python (Django REST Framework) dan PostgreSQL.",
    "Membuat API inventori untuk 3 toko UMKM dengan Flask.",
    "Built and maintained REST APIs in Python (FastAPI) serving 300k monthly active users.",
    "Developed REST APIs with Python (Flask) for the inventory module used by 40 retail stores.",
    "Membangun microservices reservasi klinik dengan Python (Django) dan PostgreSQL.",
    "Membuat endpoint REST API dengan Python (FastAPI) untuk modul absensi.",
    "Mengembangkan backend aplikasi web klien dengan Python (Flask) dan PHP.",
    "Built REST APIs with Node.js (Express) and PostgreSQL for the ordering platform.",
    "Membangun REST API dengan Laravel (PHP) dan MySQL.",
    # PostgreSQL & DB
    "Menurunkan latensi p95 API tracking dari 900 ms menjadi 180 ms dengan optimasi query PostgreSQL.",
    "Menangani lebih dari 1,2 juta transaksi per hari dengan PostgreSQL dan uptime 99,9%.",
    "Designed PostgreSQL schemas and reduced slow queries by 60% through indexing and query rewrites.",
    "Maintained the PostgreSQL database, wrote migrations and stored procedures.",
    "Menulis query PostgreSQL dan BigQuery untuk laporan penjualan harian.",
    "Prepared test data with PostgreSQL queries.",
    "Improved checkout API response time by 40% by adding database indexes.",
    "Membuat skema database relasional MySQL dan query transaksi harian.",
    # Docker & Containers & K8s
    "Men-deploy layanan dengan Docker dan Kubernetes (GKE) di Google Cloud.",
    "Mengemas seluruh layanan ke dalam container Docker.",
    "Containerized services with Docker and deployed to AWS ECS.",
    "Dockerized all services and maintained CI pipelines.",
    "Operated services on Kubernetes in Google Cloud (GKE).",
    "Menggunakan Docker untuk lingkungan pengembangan dan deployment.",
    "Ran isolated test environments with Docker.",
    "Menggunakan Docker untuk deployment ke server klien.",
    # Caching & Redis
    "Caching Redis untuk mempercepat query catalog hingga 5x lipat.",
    "Optimasi query PostgreSQL dan caching Redis.",
    "Implemented Redis distributed locks for payment reconciliation.",
    "Menggunakan Redis in-memory cache untuk session management.",
    # Cloud (AWS / GCP)
    "Men-deploy layanan ke Google Cloud Platform menggunakan Cloud Run dan GKE.",
    "Mengintegrasikan layanan dengan AWS (S3 dan SQS).",
    "Cut infrastructure cost by 35% by right-sizing Google Cloud compute instances.",
    "Membuat pipeline data dengan Python (pandas, Airflow) di Google Cloud.",
    "AWS Certified Developer – Associate — Amazon Web Services (Mei 2023)",
    "Google Cloud Professional Cloud Developer — Google Cloud (2024)",
    # Leadership & Mentoring
    "Memimpin tim 4 backend engineer, termasuk code review dan mentoring engineer junior.",
    "Mentored 5 backend engineers and ran weekly design reviews.",
    "Led a QA team of 3 engineers.",
    "Memimpin 6 sales executive untuk wilayah Jawa Timur.",
    "Ketua Himpunan Mahasiswa Informatika memimpin 30 pengurus himpunan.",
    # Education
    "S1 Teknik Informatika Universitas Teknologi Cakrawala IPK 3,61",
    "S1 Ilmu Komputer Universitas Gadjah Mada IPK 3,75",
    "S1 Sistem Informasi Universitas Pelita Nusantara",
    "S1 Teknik Komputer Institut Teknologi Harapan Bangsa",
    "S1 Matematika Terapan Universitas Padjadjaran",
    # Skills lists
    "Python, FastAPI, Django, Flask, PostgreSQL, Redis, Docker, Kubernetes, Google Cloud, Git",
    "Python, FastAPI, PostgreSQL, Docker, AWS, Git",
    "Python, Flask, PostgreSQL, Docker, Redis, Git",
    "Python, Go, PostgreSQL, Kubernetes, Docker, Google Cloud, Git",
    "Python, Django, Flask, PostgreSQL, Docker, AWS, PHP",
    "Node.js, Express, PostgreSQL, Docker, Git, Jest",
    "Python, pandas, SQL, PostgreSQL, BigQuery, Airflow, Google Cloud",
    "Python, pytest, requests, PostgreSQL, Docker, Git, CI/CD",
    "PHP, Laravel, MySQL, Vue.js, Docker, Git",
    # Non-relevant / Marginal chunks
    "Menjalankan rekrutmen end-to-end untuk 60 posisi per tahun, dari sourcing hingga offering.",
    "Mengelola administrasi payroll dan BPJS untuk 400 karyawan.",
    "Menyusun kontrak PKWT dan PKWTT sesuai UU Ketenagakerjaan.",
    "Menyusun laporan keuangan bulanan dan rekonsiliasi bank.",
    "Mengelola pelaporan PPh 21 dan PPN.",
    "Menggunakan SAP dan Microsoft Excel untuk pencatatan transaksi.",
    "Designed brand identities for 25+ hospitality clients.",
    "Produced social media content with Adobe Illustrator, Photoshop, and Figma.",
    "Mencapai 120% target penjualan tahunan pada 2024.",
    "Mengelola 80 akun pelanggan retail.",
    "asuhan keperawatan kepada pasien gawat darurat.",
    "Mendokumentasikan tindakan pada sistem rekam medis elektronik.",
    "Tugas Akhir: Sistem Antrian Puskesmas memangkas waktu tunggu rata-rata 25%.",
    "Membuat poster dan aset visual untuk kampanye promosi kafe.",
    "Melakukan rekonsiliasi kas kecil setiap akhir pekan.",
    "Melakukan pengujian manual fungsional pada aplikasi mobile Android.",
    "Menyiapkan laporan pajak tahunan badan (SPT 1771).",
    "Merawat luka pasca operasi dan memasang infus pada pasien rawat inap.",
    "Melakukan negosiasi kontrak distribusi barang konsumsi.",
    "Membuat desain kemasan produk kopi siap minum.",
]

# Duplicate/expand to exactly 100 chunks if needed
while len(CHUNKS) < 100:
    CHUNKS.append(f"Variasi pengalaman kerja tambahan {len(CHUNKS)}: backend microservices Python dan database relasional.")
CHUNKS = CHUNKS[:100]

# Queries corresponding to JD-01 requirements and their true relevant keywords/indices
TEST_QUERIES = [
    {
        "req": "R1 (Python Backend)",
        "query": "Pengalaman pemrograman backend Python FastAPI Django",
        "gold_keyword": "Python",
    },
    {
        "req": "R2 (PostgreSQL Database)",
        "query": "Desain database PostgreSQL optimasi query indexing",
        "gold_keyword": "PostgreSQL",
    },
    {
        "req": "R3 (Scale / Microservices)",
        "query": "Arsitektur microservices menangani jutaan transaksi skala besar",
        "gold_keyword": "transaksi",
    },
    {
        "req": "R4 (Docker & Container)",
        "query": "Containerization Docker Kubernetes deployment",
        "gold_keyword": "Docker",
    },
    {
        "req": "R5 (Redis Caching)",
        "query": "Caching Redis in-memory latensi rendah",
        "gold_keyword": "Redis",
    },
    {
        "req": "R6 (Cloud GCP/AWS)",
        "query": "Cloud infrastructure Google Cloud GKE AWS S3",
        "gold_keyword": "Cloud",
    },
    {
        "req": "R7 (Leadership & Mentoring)",
        "query": "Memimpin tim software engineer code review mentoring",
        "gold_keyword": "Memimpin",
    },
    {
        "req": "R10 (Degree Informatika)",
        "query": "Pendidikan S1 Teknik Informatika Ilmu Komputer",
        "gold_keyword": "Informatika",
    },
]


def benchmark_model(model_id: str, short_name: str) -> dict:
    print(f"\n==========================================")
    print(f"Loading model: {model_id} ({short_name})...")
    t0 = time.time()
    try:
        model = SentenceTransformer(model_id, device="cpu")
        load_time = time.time() - t0
        print(f"Loaded in {load_time:.2f}s")
    except Exception as e:
        print(f"FAILED to load {model_id}: {e}")
        return {"model": short_name, "error": str(e)}

    # Warmup
    _ = model.encode(["warmup text"], show_progress_bar=False)

    # Encode 100 chunks
    t_start = time.time()
    chunk_embeddings = model.encode(CHUNKS, batch_size=32, show_progress_bar=False, normalize_embeddings=True)
    encode_time = time.time() - t_start
    dim = chunk_embeddings.shape[1]
    print(f"Encoded 100 chunks in {encode_time:.2f}s (dim={dim}) | Throughput: {100/encode_time:.1f} chunks/sec")

    # Evaluate retrieval top-3 accuracy
    top3_hits = 0
    total_q = len(TEST_QUERIES)

    for q in TEST_QUERIES:
        q_emb = model.encode([q["query"]], show_progress_bar=False, normalize_embeddings=True)[0]
        # Cosine similarity (already normalized, dot product = cosine)
        sims = np.dot(chunk_embeddings, q_emb)
        top3_indices = np.argsort(sims)[::-1][:3]
        top3_texts = [CHUNKS[idx] for idx in top3_indices]
        
        hit = any(q["gold_keyword"].lower() in t.lower() for t in top3_texts)
        if hit:
            top3_hits += 1
            print(f"  ✓ {q['req']}: Top-1 sim={sims[top3_indices[0]]:.3f} -> '{top3_texts[0][:60]}...'")
        else:
            print(f"  ✗ {q['req']}: Miss! Top-1 sim={sims[top3_indices[0]]:.3f} -> '{top3_texts[0][:60]}...'")

    accuracy = (top3_hits / total_q) * 100
    print(f"Top-3 Retrieval Accuracy: {top3_hits}/{total_q} ({accuracy:.1f}%)")

    return {
        "model": short_name,
        "model_id": model_id,
        "dim": dim,
        "encode_time_100": round(encode_time, 2),
        "throughput": round(100 / encode_time, 1),
        "top3_accuracy": accuracy,
    }


def main():
    models = [
        ("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", "MiniLM-L12-v2"),
        ("microsoft/harrier-oss-v1-270m", "harrier-oss-v1-270m"),
        ("Qwen/Qwen3-Embedding-0.6B", "Qwen3-Embedding-0.6B"),
    ]

    results = []
    for mid, name in models:
        res = benchmark_model(mid, name)
        results.append(res)

    print("\n\n==========================================")
    print("=== SUMMARY BENCHMARK HASIL (CPU VPS) ===")
    print("==========================================")
    for r in results:
        if "error" in r:
            print(f"{r['model']}: ERROR ({r['error']})")
        else:
            print(f"- {r['model']} ({r['dim']}d): Waktu 100 chunks = {r['encode_time_100']}s ({r['throughput']} chunks/s) | Top-3 Accuracy = {r['top3_accuracy']}%")


if __name__ == "__main__":
    main()
