# 04. Tahap 4: Temporal Engine — Sweep-Line Weighted Calendar Union

Dokumen ini menjelaskan implementasi mesin penghitung durasi kalender (*Temporal Engine*) pada modul `src/domain/temporal/date_normalizer.py` dan `src/domain/temporal/weighted_union.py`. Modul ini bertanggung jawab mengevaluasi kriteria durasi pengalaman kerja (misal: *"Minimal 2 tahun sebagai Backend Developer"*) menggunakan matematika interval murni tanpa melibatkan tebakan LLM.

---

## 1. Masalah Fatal: Mengapa LLM Dilarang Menghitung Tanggal

Model bahasa besar (LLM) dilatih untuk memprediksi kata berikutnya, bukan melakukan aritmatika interval kalender. Ketika disuruh menghitung durasi kerja pelamar, LLM sering melakukan kesalahan fatal:

1. **Ilusi Pekerjaan Bertumpuk (*Concurrent/Overlap Jobs*):**  
   Jika pelamar bekerja di Perusahaan X dari Januari 2022 s.d. Desember 2023 (24 bulan) dan di saat yang sama menjadi *freelancer* di Klien Y dari Juni 2022 s.d. Juni 2023 (12 bulan), LLM sering menjumlahkan keduanya menjadi $24 + 12 = 36\text{ bulan}$. Padahal waktu kalender yang berjalan di dunia nyata hanya **24 bulan**.
2. **Magang & Paruh Waktu Dihitung Penuh:**  
   LLM sering memperlakukan magang 6 bulan setara dengan kerja senior 6 bulan, tanpa mempertimbangkan bobot intensitas kerja.
3. **Halusinasi Format Waktu Indonesia/Inggris:**  
   Format penulisan acak seperti *"Agt 2023 - Sekarang"*, *"01/21 - 12/22"*, atau *"2020 - 2024"* sering disalahartikan durasinya.

---

## 2. Normalisasi Format Tanggal (`date_normalizer.py`)

Modul `date_normalizer.py` membedah dan menstandarkan semua bentuk penulisan tanggal di CV pelamar ke dalam representasi kalender ISO-8601 (`YYYY-MM`):

```python
@dataclass
class NormalizedDate:
    year: int
    month: int                  # 1 - 12 (default 1 jika hanya tahun)
    precision: DatePrecision    # EXACT_MONTH, YEAR_ONLY, RELATIVE_PRESENT
    raw_text: str
```

### Kamus Bulan Bahasa Indonesia & Inggris:
Modul mendukung singkatan dan penamaan lokal:
- `Januari`, `Jan`, `January` ➔ Bulan `01`
- `Februari`, `Feb`, `February` ➔ Bulan `02`
- `Maret`, `Mar`, `March` ➔ Bulan `03`
- `Agustus`, `Agu`, `Agt`, `Aug` ➔ Bulan `08`
- `Oktober`, `Okt`, `Oct` ➔ Bulan `10`
- `Desember`, `Des`, `Dec` ➔ Bulan `12`

### Penanganan Kata Kunci Dinamis (*Relative Dates*):
Kata-kata seperti *"Sekarang"*, *"Present"*, *"Saat ini"*, *"Current"* otomatis dipetakan ke bulan dan tahun saat evaluasi dijalankan (misal: Oktober 2026), sehingga jam terbang kandidat yang masih aktif bekerja terhitung akurat sampai hari ini.

---

## 3. Algoritma Garis Sapuan (*Sweep-Line Weighted Calendar Union*)

Untuk menghitung akumulasi waktu kerja riil tanpa menghitung ganda periode overlap, sistem menggunakan algoritma garis waktu berbasis titik kejadian (*Sweep-Line Event Points*) di `weighted_union.py`:

```text
CONTOH KASUS PELAMAR:
Pekerjaan 1 (Full-time): Jan 2022 ──────────────────────► Des 2023 (Bobot: 1.0)
Pekerjaan 2 (Freelance):        Jun 2022 ──────► Jun 2023          (Bobot: 0.5)

GARIS WAKTU KALENDER (SWEEP-LINE):
Bulan:   Jan 2022       Jun 2022       Jun 2023       Des 2023
Interval: [─── 5 bln ───][─── 13 bln ──][─── 6 bln ────]
Bobot:     1.0            max(1.0, 0.5)  1.0

HASIL AKUMULASI WAKTU NYATA:
= (5 x 1.0) + (13 x 1.0) + (6 x 1.0) = 24 Bulan Kalender Terbukti!
(Tidak dihitung ganda menjadi 36 bulan!).
```

### Pembobotan Tipe Pekerjaan (*Employment Weighting*):
Sistem memungkinkan pembobotan nilai jam terbang sesuai intensitas kerja:
- **Full-time (Penuh Waktu):** Bobot `1.0` (100% dihitung penuh).
- **Internship (Magang):** Bobot `0.5` (6 bulan magang = 3 bulan pengalaman industri).
- **Part-time / Freelance:** Bobot `0.5` s.d. `0.75`.
- **Contract:** Bobot `1.0`.

---

## 4. Buku Kas Kalender (*Monthly Ledger Representation*)

Untuk transparansi dan reproduksibilitas audit, modul `weighted_union.py` menghasilkan sebuah **Buku Kas Kalender (Month Ledger)**:

```json
{
  "total_calendar_months": 33,
  "weighted_months": 31.5,
  "ledger": {
    "2022-01": {"roles": ["Backend Developer"], "effective_weight": 1.0},
    "2022-02": {"roles": ["Backend Developer"], "effective_weight": 1.0},
    "...": "...",
    "2023-06": {"roles": ["Backend Developer", "Freelance Web"], "effective_weight": 1.0}
  }
}
```

Buku kas ini membuktikan bulan demi bulan di mana kandidat aktif berkarya. Jika rekruter menanyakan: *"Dari mana angka 33 bulan ini didapat?"*, sistem dapat menampilkan daftar bulan kalender eksak beserta nama instansi tempat kandidat bekerja.

---

## 5. Evaluasi Kriteria Durasi pada Graph B

Ketika kriteria lowongan mencantumkan syarat durasi (misal kriteria `R1`: *"Minimal 2 tahun sebagai Backend Developer"* = 24 bulan):
1. **Penyaringan Domain Relevan:**  
   Sistem hanya menjumlahkan bulan kalender di mana kandidat memegang posisi atau mengerjakan proyek pada **domain yang relevan** (misal hanya domain backend; posisi sales atau admin gudang tidak ikut dijumlahkan).
2. **Evaluasi Deterministik Status:**
   - Jika $\text{Bulan Relevan} \ge \text{Target (24 bulan)}$ ➔ Status kriteria: **`STRONG`** (Level L2/L3).
   - Jika $\text{Bulan Relevan} \ge 0.5 \times \text{Target (12 - 23 bulan)}$ ➔ Status kriteria: **`PARTIAL`** (Level L1).
   - Jika $\text{Bulan Relevan} < 0.5 \times \text{Target}$ ➔ Status kriteria: **`NONE`** (Level L0).

Dengan cara ini, keabsahan jam terbang kandidat diuji dengan landasan matematika yang tidak terbantahkan, bebas dari bias subjektif atau kesalahan kalkulasi LLM! 🚀
