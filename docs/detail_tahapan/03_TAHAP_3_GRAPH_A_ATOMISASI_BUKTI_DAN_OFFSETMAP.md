# 03. Tahap 3: Graph A — Atomisasi Bukti & OffsetMap Dwiarah

Tahap 3 adalah inti dari proses pemprofilan dokumen (*Document Profiling*) pada **Graph A**. Alih-alih memperlakukan riwayat CV sebagai satu paragraf panjang yang tidak terstruktur, sistem memecah seluruh riwayat kandidat menjadi satuan-satuan bukti independen terkecil yang disebut **Evidence Atoms**, lengkap dengan alamat koordinat visual pada berkas PDF aslinya melalui **OffsetMap Dwiarah**.

---

## 1. Konsep Dasar Evidence Atoms (*Grounding by Construction*)

Dalam hukum dan audit rekrutmen, sebuah klaim kompetensi harus dapat ditelusuri ke kalimat persisnya. 

**Evidence Atom** adalah representasi data formal dari satu butir fakta pengalaman, keahlian, atau pendidikan seorang kandidat. Modul `src/domain/atoms.py` memecah teks riwayat pelamar menjadi entitas atomik:

```python
@dataclass
class EvidenceAtom:
    id: str                      # Identifier unik, contoh: E1.B1, E2.H1
    profile_id: uuid.UUID        # Relasi ke kandidat
    kind: AtomKind               # Jenis atom
    text: str                    # Teks bukti bersih (tersanitasi)
    source_bbox: BoundingBox     # Koordinat fisik kotak di PDF (page, x0, y0, x1, y1)
    char_start: int              # Posisi karakter awal di teks tersensor
    char_end: int                # Posisi karakter akhir di teks tersensor
    temporal_context: str | None # Rentang tahun/bulan pengalaman (misal: "2022 - 2024")
    role_title: str | None       # Konteks jabatan (misal: "Backend Engineer")
```

### Klasifikasi Jenis Atom (`AtomKind`):
1. `EXP_HEADER` (`E*.H1`): Judul posisi kerja, nama instansi/perusahaan, dan rentang tanggal kerja.
2. `EXP_BULLET` (`E*.B1`, `E*.B2`): Kalimat uraian tugas, tanggung jawab, dan dampak kerja di tempat kerja tersebut.
3. `PROJECT_BULLET` (`P*.B1`): Deskripsi proyek spesifik, portofolio, atau aplikasi yang pernah dibangun.
4. `SUMMARY_SENTENCE` (`S1.B1`): Klaim mandiri pelamar pada bagian ringkasan profil (*Bio / Executive Summary*).
5. `SKILL_LIST_ITEM` (`T0.B1`): Daftar kata kunci keahlian yang tercantum di kolom keahlian (*Skills List*).
6. `EDUCATION` (`ED1`): Riwayat pendidikan formal (Gelar, Universitas, Jurusan, IPK).
7. `CERT` (`C1`): Lisensi profesi dan sertifikasi terverifikasi.

---

## 2. Tingkat Keandalan Sumber Bukti (Tiers of Evidence)

Sistem membedakan bobot keandalan sumber bukti untuk mencegah kecurangan *keyword stuffing*:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                   TIER BUKTI BERDASARKAN KEANDALAN                     │
├─────────┬───────────────────┬──────────────────────────────────────────┤
│ Tier    │ Kode Jenis Atom   │ Nilai Keandalan Hukum & Integritas       │
├─────────┼───────────────────┼──────────────────────────────────────────┤
│ Tier 3  │ EXP_BULLET        │ TERTINGGI: Bukti pekerjaan nyata di      │
│         │ PROJECT_BULLET    │ kantor/perusahaan dengan konteks riil.   │
├─────────┼───────────────────┼──────────────────────────────────────────┤
│ Tier 2  │ EDUCATION, CERT   │ SEDANG: Bukti pendidikan formal dan      │
│         │                   │ sertifikasi berlisensi.                  │
├─────────┼───────────────────┼──────────────────────────────────────────┤
│ Tier 0  │ SKILL_LIST_ITEM   │ TERENDAH: Sekadar klaim kata di daftar   │
│ (T0)    │ SUMMARY_SENTENCE  │ keahlian tanpa ada bukti dipakai kerja.  │
└─────────┴───────────────────┴──────────────────────────────────────────┘
```

> **Aturan Kunci Anti-Stuffing:**  
> Jika seorang pelamar hanya memiliki bukti dari **Tier 0 (T0)** untuk suatu kriteria teknologi, sistem secara otomatis mengunci nilai maksimalnya di tingkat **`PARTIAL` (Level L0)**. Pelamar tidak akan pernah bisa meraih predikat `STRONG` jika teknologinya cuma dipajang di bio tanpa pernah digunakan dalam proyek atau pekerjaan riil!

---

## 3. Peta Offset Dwiarah (*Bi-directional OffsetMap*)

Tantangan teknis utama saat menerapkan sensor data pribadi (PII) adalah:  
*"Ketika kata 'Budi Setiawan' disensor menjadi '[NAMA_TERSEMBUNYI]', panjang karakter berubah. Bagaimana cara sistem mengetahui posisi koordinat kotak PDF aslinya?"*

Modul `OffsetMap` memecahkan masalah ini dengan mencatat setiap pergeseran karakter:

```text
TEKS ASLI PDF:
"Hubungi Budi Setiawan di nomor 08123456789 untuk wawancara teknis."
 [0]    [8]           [21]      [31]        [42]

TEKS TERSENSOR:
"Hubungi [NAMA] di nomor [KONTAK_HR] untuk wawancara teknis."
 [0]    [8]    [14]     [24]        [35]
```

### Struktur `OffsetSegment`:
```python
@dataclass
class OffsetSegment:
    orig_start: int  # Posisi awal karakter di teks mentah PDF
    orig_end: int    # Posisi akhir karakter di teks mentah PDF
    red_start: int   # Posisi awal karakter di teks tersensor
    red_end: int     # Posisi akhir karakter di teks tersensor
    is_pii: bool     # Apakah segmen ini merupakan hasil sensor
```

### Kemampuan Dwiarah (*Bi-directional*):
1. **Maju (`redacted_to_original`):**  
   Ketika AI Matcher mengevaluasi teks tersensor pada karakter ke-50, sistem dapat menghitung kembali bahwa di berkas aslinya teks tersebut berada di karakter ke-68.
2. **Mundur (`original_to_redacted`):**  
   Memetakan koordinat fisik PDF kembali ke string yang sedang dianalisis oleh AI.

---

## 4. Ekstraksi Koordinat Visual PyMuPDF (*Visual Bounding Boxes*)

Selain teks mentah, modul `src/domain/atoms.py` mengekstrak koordinat kotak pembatas fisik (*Bounding Box / Rect*) dari setiap baris teks:

```python
@dataclass
class BoundingBox:
    page_number: int  # Nomor halaman dokumen (1-indexed)
    x0: float         # Jarak dari tepi kiri kertas (point)
    y0: float         # Jarak dari tepi atas kertas (point)
    x1: float         # Jarak tepi kanan kotak teks (point)
    y1: float         # Jarak tepi bawah kotak teks (point)
```

### Visual Highlighting di Frontend:
Data koordinat ini dikirim ke frontend React. Ketika rekruter mengklik sebuah bukti di laci kandidat (*Candidate Detail Drawer*):
- Antarmuka web memuat pratinjau halaman PDF asli.
- Sebuah lapisan sorotan kuning transparan (*highlight overlay*) otomatis digambar persis di atas koordinat `[x0, y0, x1, y1]` kalimat bukti tersebut.
- Rekruter dapat langsung memverifikasi keaslian kalimat tanpa perlu membaca manual seluruh isi dokumen pelamar.

---

## 5. Ringkasan Keuntungan Graph A

Dengan arsitektur Evidence Atomizer ini:
1. **Sekali Ekstraksi, Dipakai Berulang Kali:** Dokumen kandidat hanya perlu di-profilkan sekali di Graph A, lalu dapat digunakan untuk melamar di ratusan posisi lowongan kerja berbeda di Graph B tanpa harus membaca ulang berkas PDF.
2. **Kekebalan Halusinasi:** Keputusan AI dipaksa bersandar pada bukti atomik riil, bukan generalisasi teks.
3. **Kepatuhan Privasi Penuh:** Analisis LLM dijalankan sepenuhnya di atas teks tersensor tanpa kehilangan kemampuan visualisasi dokumen aslinya.
