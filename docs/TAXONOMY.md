# Panduan Ekstensi Taksonomi Domain (FX-31)

Platform CV Screening menggunakan sistem taksonomi berbasis berkas konfigurasi YAML di folder `config/taxonomy/`. Seluruh pengenalan jabatan, alias keahlian, istilah sertifikasi, dan aturan kepemimpinan dikendalikan oleh berkas-berkas ini **tanpa perlu mengubah kode sumber Python**.

---

## 1. Struktur Berkas Taksonomi

Folder `config/taxonomy/` berisi:
- `role_families.yaml`: Klasifikasi jabatan (misalnya `backend`, `frontend`, `data`, `civil_engineering`, `hr`, `finance`).
- `skills.yaml`: Konsep keahlian, alias, relasi, dan kategori bobot.
- `certifications.yaml`: Istilah pencocokan sertifikasi profesional (mis. `cert:cloud`, `cert:hr`, `cert:safety_civil`).
- `leadership.yaml`: Kata kerja aksi dan kata kunci jabatan kepemimpinan.
- `prohibited_criteria.yaml`: Leksikon deteksi kriteria diskriminatif (PROHIBITED) dan syarat administratif (ADMIN_DEMOGRAPHIC).
- `stopwords.txt`: Kata henti umum dalam bahasa Indonesia dan Inggris.

---

## 2. Cara Menambahkan Role Baru (Contoh: `data_analyst`)

### Langkah 1: Tambahkan Role Family di `role_families.yaml`
Buka `config/taxonomy/role_families.yaml` dan tambahkan blok baru:

```yaml
data_analyst:
  titles:
    - data analyst
    - analis data
    - junior data analyst
    - senior data analyst
    - bi analyst
    - business intelligence analyst
  domain_terms:
    - sql
    - python
    - dashboard
    - power bi
    - tableau
    - data visualization
    - reporting
  related:
    - data
    - business_analyst
```

### Langkah 2: Tambahkan Keahlian / Konsep di `skills.yaml`
Buka `config/taxonomy/skills.yaml` dan daftarkan konsep atau alias spesifik:

```yaml
skill:power_bi:
  label: Power BI
  type: tool
  category: HARD_SKILLS
  kind: SKILL
  default_importance: STRONG_PREFERENCE
  default_weight: 8.0
  aliases:
    - power bi
    - powerbi
    - power-bi
    - dax

field:data_analytics:
  label: Sains Data & Statistika
  aliases:
    - sains data
    - data science
    - statistika
    - statistics
    - matematika
```

### Langkah 3: Verifikasi Otomatis
Setelah berkas YAML disimpan, aplikasi akan otomatis memvalidasi regex saat startup. Untuk memverifikasi sintaks dan integritas:

```bash
make test
```

Aplikasi langsung mengenali kandidat dengan jabatan dan istilah tersebut tanpa perlu restart engine atau penulisan kode baru.
