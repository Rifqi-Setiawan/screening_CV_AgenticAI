#!/usr/bin/env python3
"""Extended Embedding Benchmark (60+ pairs) comparing MiniLM-L12-v2, harrier-oss-v1-270m, and Qwen3-Embedding-0.6B.
Measures Top-1 and Top-3 retrieval accuracy separated for Indonesian and English CVs.
"""
from __future__ import annotations

import time
import numpy as np
from sentence_transformers import SentenceTransformer

# 64 pairs of (Query, Target Bullet / True Evidence Chunk, Language)
# Extracted directly from CV content
PAIRS = [
    # --- INDONESIAN CVs (34 pairs) ---
    # R1: Python Backend
    ("Pengalaman pengembangan backend dengan Python FastAPI", "Mendesain arsitektur microservices berbasis Python (FastAPI) untuk sistem pelacakan paket.", "id"),
    ("Membangun REST API pembayaran menggunakan Python Django", "Membangun REST API pembayaran dengan Python (Django REST Framework) dan PostgreSQL.", "id"),
    ("Pembuatan API inventori toko dengan framework Flask", "Membuat API inventori untuk 3 toko UMKM dengan Flask.", "id"),
    ("Layanan reservasi klinik berbasis Python Django", "Membangun microservices reservasi klinik dengan Python (Django) dan PostgreSQL.", "id"),
    ("Backend aplikasi web klien dengan Python Flask", "Mengembangkan backend aplikasi web klien dengan Python (Flask) dan PHP.", "id"),
    ("Endpoint REST API absensi dengan Python FastAPI", "Membuat endpoint REST API dengan Python (FastAPI) untuk modul absensi.", "id"),
    ("Daftar keahlian bahasa pemrograman Python", "Keahlian: Python, FastAPI, Django, Flask, PostgreSQL, Redis, Docker, Git", "id"),
    # R2: PostgreSQL Database
    ("Optimasi query PostgreSQL dan penurunan latensi p95", "Menurunkan latensi p95 API tracking dari 900 ms menjadi 180 ms dengan optimasi query PostgreSQL dan caching Redis.", "id"),
    ("Skema database relasional PostgreSQL transaksi tinggi", "Menangani lebih dari 1,2 juta transaksi per hari dengan Python dan PostgreSQL.", "id"),
    ("Database PostgreSQL microservices reservasi", "Membangun microservices reservasi klinik dengan Python (Django) dan PostgreSQL.", "id"),
    ("Query database PostgreSQL dan BigQuery", "Menulis query PostgreSQL dan BigQuery untuk laporan penjualan harian.", "id"),
    ("Menulis query database PostgreSQL modul absensi", "Menulis query PostgreSQL dan memperbaiki bug.", "id"),
    ("Database relasional PostgreSQL", "Keahlian: Python, FastAPI, PostgreSQL, Docker, Redis", "id"),
    # R3: Skala Besar & Microservices
    ("Arsitektur microservices berskala besar", "Mendesain arsitektur microservices berbasis Python (FastAPI) untuk sistem pelacakan paket.", "id"),
    ("Menangani jutaan transaksi per hari uptime 99.9%", "Menangani lebih dari 1,2 juta transaksi per hari dengan uptime 99,9%.", "id"),
    ("Layanan microservices reservasi kesehatan digital", "Membangun microservices reservasi klinik dengan Python (Django) dan PostgreSQL.", "id"),
    ("Sistem antrian web memangkas waktu tunggu puskesmas", "Sistem antrian berbasis web yang dipakai 3 puskesmas dan memangkas waktu tunggu rata-rata 25%.", "id"),
    # R4: Docker & Container
    ("Deploy layanan menggunakan Docker dan Kubernetes GKE", "Men-deploy layanan dengan Docker dan Kubernetes (GKE) di Google Cloud.", "id"),
    ("Mengemas seluruh microservices ke container Docker", "Mengemas seluruh layanan ke dalam container Docker.", "id"),
    ("Docker untuk lingkungan pengembangan dan deployment", "Menggunakan Docker untuk lingkungan pengembangan dan deployment.", "id"),
    ("Container Docker deployment server klien", "Menggunakan Docker untuk deployment ke server klien.", "id"),
    # R5: Caching Redis
    ("Caching Redis untuk optimasi performa backend", "Menurunkan latensi p95 API tracking dari 900 ms menjadi 180 ms dengan optimasi query PostgreSQL dan caching Redis.", "id"),
    ("Keahlian Redis in-memory data store", "Python, FastAPI, Django, Flask, PostgreSQL, Redis, Docker, Kubernetes, Google Cloud, Git", "id"),
    # R6: Cloud Provider (GCP / AWS)
    ("Deployment Google Cloud Platform GKE", "Men-deploy layanan dengan Docker dan Kubernetes (GKE) di Google Cloud.", "id"),
    ("Integrasi layanan cloud AWS S3 dan SQS", "Mengintegrasikan layanan dengan AWS (S3 dan SQS).", "id"),
    ("Pipeline data Airflow di Google Cloud", "Membuat pipeline data dengan Python (pandas, Airflow) di Google Cloud.", "id"),
    ("Sertifikasi cloud AWS Certified Developer Associate", "AWS Certified Developer – Associate — Amazon Web Services (Mei 2023)", "id"),
    # R7: Leadership & Mentoring
    ("Memimpin tim backend engineer dan mentoring junior", "Memimpin tim 4 backend engineer, termasuk code review dan mentoring engineer junior.", "id"),
    ("Kepemimpinan organisasi ketua himpunan mahasiswa", "Ketua Himpunan Mahasiswa Informatika memimpin 30 pengurus himpunan.", "id"),
    ("Memimpin sales executive mencapai target", "Memimpin 6 sales executive untuk wilayah Jawa Timur.", "id"),
    # R9: REST API Design
    ("Desain arsitektur REST API pembayaran", "Membangun REST API pembayaran dengan Python (Django REST Framework) dan PostgreSQL.", "id"),
    ("REST API internal untuk data dashboard", "Membuat API internal sederhana dengan Flask untuk menyuplai data dashboard.", "id"),
    # R10: Pendidikan S1
    ("Pendidikan S1 Teknik Informatika", "S1 Teknik Informatika Universitas Teknologi Cakrawala 2015 – 2019 IPK 3,61", "id"),
    ("Lulusan sarjana S1 Informatika Nusantara", "S1 Teknik Informatika – Universitas Lembayung Nusantara (2016 – 2020) IPK 3,55", "id"),

    # --- ENGLISH CVs (30 pairs) ---
    # R1: Python Backend
    ("Python FastAPI backend API development", "Built and maintained REST APIs in Python (FastAPI) serving 300k monthly active users.", "en"),
    ("Microservices migration to Go and Python", "Led the migration from a monolith to Go and Python microservices.", "en"),
    ("Python test automation with pytest", "Built API test automation with Python (pytest, requests) covering 120+ REST endpoints.", "en"),
    ("Python backend programming skill", "Skills: Python, FastAPI, PostgreSQL, Docker, AWS, Git", "en"),
    ("Python and Go languages backend development", "Skills: Python, Go, PostgreSQL, Kubernetes, Docker, Google Cloud, Git", "en"),
    # R2: PostgreSQL Database
    ("PostgreSQL schema design and query optimization", "Designed PostgreSQL schemas and reduced slow queries by 60% through indexing and query rewrites.", "en"),
    ("PostgreSQL database indexing response time", "Improved checkout API response time by 40% by adding database indexes.", "en"),
    ("Test data preparation using PostgreSQL", "Prepared test data with PostgreSQL queries.", "en"),
    ("PostgreSQL database skill", "Skills: Node.js, Express, PostgreSQL, Docker, Git, Jest", "en"),
    # R3: High Scale & Microservices
    ("High scale REST API serving hundreds of thousands users", "Built and maintained REST APIs in Python (FastAPI) serving 300k monthly active users.", "en"),
    ("Monolith to microservices architecture migration", "Led the migration from a monolith to Go and Python microservices.", "en"),
    ("Checkout ordering platform performance optimization", "Improved checkout API response time by 40% by adding database indexes.", "en"),
    # R4: Docker & Containers & Kubernetes
    ("Containerized microservices Docker AWS ECS", "Containerized services with Docker and deployed to AWS ECS.", "en"),
    ("Kubernetes cluster operations Google Cloud GKE", "Operated services on Kubernetes in Google Cloud (GKE).", "en"),
    ("Dockerized services and CI pipelines maintenance", "Dockerized all services and maintained CI pipelines.", "en"),
    ("Isolated test environments with Docker", "Ran isolated test environments with Docker.", "en"),
    # R5: Caching & Redis
    ("Redis in-memory caching for performance", "Reduced API response times by implementing Redis caching for product catalogs.", "en"),
    ("Redis key-value store skills", "Skills: Python, Flask, PostgreSQL, Docker, Redis, Git", "en"),
    # R6: Cloud Infrastructure (AWS / GCP)
    ("AWS cloud deployment ECS and RDS", "Containerized services with Docker and deployed to AWS ECS.", "en"),
    ("Google Cloud GKE cost optimization", "Cut infrastructure cost by 35% by right-sizing Google Cloud compute instances.", "en"),
    ("Cloud certification Google Cloud Professional Developer", "Google Cloud Professional Cloud Developer — Google Cloud (2024)", "en"),
    ("Cloud services AWS integration", "Skills: Python, Django, Flask, PostgreSQL, Docker, AWS, PHP", "en"),
    # R7: Leadership & Engineering Mentoring
    ("Mentoring backend engineers design reviews", "Mentored 5 backend engineers and ran weekly design reviews.", "en"),
    ("Lead QA automation team leadership", "Led a QA team of 3 engineers.", "en"),
    # R8: CI/CD Pipelines
    ("Maintained continuous integration CI pipelines", "Dockerized all services and maintained CI pipelines.", "en"),
    ("Test automation in CI/CD pipeline", "Reduced regression testing time by 50% by integrating test suites into CI.", "en"),
    # R9: REST API Design
    ("REST API design for ordering platform", "Built REST APIs with Node.js (Express) and PostgreSQL for the ordering platform.", "en"),
    ("Automated testing for REST API endpoints", "Built API test automation with Python (pytest, requests) covering 120+ REST endpoints.", "en"),
    # R10: Computer Science Degree
    ("Bachelor of Computer Science degree", "Bachelor of Computer Science, Gadjah Mada University, GPA 3.75", "en"),
    ("Computer Engineering undergraduate degree", "B.S. in Computer Engineering, Bandung Institute of Technology", "en"),
]

# Corpus of chunks: target chunks plus distractors from real CVs
CORPUS = list({p[1] for p in PAIRS})
# Add 36 distractors to reach 100 corpus chunks
DISTRACTORS = [
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
    "Memberikan pelatihan orientasi karyawan baru.",
    "Mengatur jadwal wawancara user dengan kandidat.",
    "Menyiapkan surat peringatan dan mediasi hubungan industrial.",
    "Memeriksa kelengkapan bukti potong pajak PPh 23.",
    "Membuat laporan arus kas mingguan.",
    "Merancang wireframe aplikasi mobile e-commerce.",
    "Menyiapkan prototipe interaktif di Figma.",
    "Melakukan presentasi produk kepada calon distributor baru.",
    "Mengikuti tender pengadaan barang logistik instansi swasta.",
    "Melakukan triase pasien pada instalasi gawat darurat rumah sakit.",
    "Mengelola stok obat-obatan emergensi di ruang resusitasi.",
    "Mengembangkan modul backend otentikasi JWT.",
    "Memperbaiki bug pada cronjob sinkronisasi data transaksi.",
    "Menulis unit test dengan coverage di atas 80 persen.",
    "Menyusun dokumentasi teknis REST API menggunakan OpenAPI Swagger.",
    "Melakukan deployment otomatis menggunakan GitHub Actions.",
]
for d in DISTRACTORS:
    if d not in CORPUS:
        CORPUS.append(d)
CORPUS = CORPUS[:100]


def run_benchmark(model_id: str, short_name: str) -> dict:
    print(f"\n==========================================")
    print(f"Evaluating model: {model_id} ({short_name})...")
    t0 = time.time()
    model = SentenceTransformer(model_id, device="cpu")
    load_time = time.time() - t0
    print(f"Loaded in {load_time:.2f}s")

    # Encode corpus
    t_start = time.time()
    corpus_embeddings = model.encode(CORPUS, batch_size=32, show_progress_bar=False, normalize_embeddings=True)
    encode_time = time.time() - t_start

    # Evaluate all pairs
    top1_total = top3_total = 0
    top1_id = top3_id = total_id = 0
    top1_en = top3_en = total_en = 0

    for query, target_chunk, lang in PAIRS:
        q_emb = model.encode([query], show_progress_bar=False, normalize_embeddings=True)[0]
        sims = np.dot(corpus_embeddings, q_emb)
        ranked_indices = np.argsort(sims)[::-1]
        ranked_texts = [CORPUS[idx] for idx in ranked_indices]

        # Is target chunk in top-1 or top-3?
        hit_top1 = (target_chunk == ranked_texts[0])
        hit_top3 = (target_chunk in ranked_texts[:3])

        if hit_top1:
            top1_total += 1
        if hit_top3:
            top3_total += 1

        if lang == "id":
            total_id += 1
            if hit_top1:
                top1_id += 1
            if hit_top3:
                top3_id += 1
        else:
            total_en += 1
            if hit_top1:
                top1_en += 1
            if hit_top3:
                top3_en += 1

    total_pairs = len(PAIRS)
    res = {
        "model": short_name,
        "dim": corpus_embeddings.shape[1],
        "encode_time_100": round(encode_time, 2),
        "throughput": round(len(CORPUS) / encode_time, 1),
        "total_pairs": total_pairs,
        "top1_all": round((top1_total / total_pairs) * 100, 1),
        "top3_all": round((top3_total / total_pairs) * 100, 1),
        "id_pairs": total_id,
        "top1_id": round((top1_id / total_id) * 100, 1),
        "top3_id": round((top3_id / total_id) * 100, 1),
        "en_pairs": total_en,
        "top1_en": round((top1_en / total_en) * 100, 1),
        "top3_en": round((top3_en / total_en) * 100, 1),
    }

    print(f"Results for {short_name}:")
    print(f"  ALL ({total_pairs} pairs) -> Top-1: {res['top1_all']}% | Top-3: {res['top3_all']}%")
    print(f"  ID  ({total_id} pairs) -> Top-1: {res['top1_id']}% | Top-3: {res['top3_id']}%")
    print(f"  EN  ({total_en} pairs) -> Top-1: {res['top1_en']}% | Top-3: {res['top3_en']}%")
    print(f"  Speed -> {res['encode_time_100']}s / 100 chunks ({res['throughput']} chunks/s)")
    return res


def main():
    models = [
        ("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", "MiniLM-L12-v2"),
        ("microsoft/harrier-oss-v1-270m", "harrier-oss-v1-270m"),
        ("Qwen/Qwen3-Embedding-0.6B", "Qwen3-Embedding-0.6B"),
    ]

    all_res = []
    for mid, sname in models:
        all_res.append(run_benchmark(mid, sname))

    print("\n\n==========================================================================")
    print("=== SUMMARY BENCHMARK 64 PASANGAN UJI (INDONESIA vs INGGRIS) DI CPU ===")
    print("==========================================================================")
    for r in all_res:
        print(f"[{r['model']} - {r['dim']}d]")
        print(f"  • Semua ({r['total_pairs']} pasang): Top-1 = {r['top1_all']}% | Top-3 = {r['top3_all']}%")
        print(f"  • CV Indonesia ({r['id_pairs']} pasang): Top-1 = {r['top1_id']}% | Top-3 = {r['top3_id']}%")
        print(f"  • CV Inggris   ({r['en_pairs']} pasang): Top-1 = {r['top1_en']}% | Top-3 = {r['top3_en']}%")
        print(f"  • Throughput: {r['encode_time_100']}s per 100 potongan ({r['throughput']} chunks/s)\n")


if __name__ == "__main__":
    main()
