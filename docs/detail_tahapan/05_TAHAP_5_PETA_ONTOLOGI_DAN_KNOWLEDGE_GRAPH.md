# 05. Tahap 5: Peta Ontologi & Knowledge Graph

Dokumen ini menjelaskan struktur kamus deklaratif, semantik hubungan logika, algoritma penelusuran graf (*graph traversal*), dan peran ontologi sebagai fondasi kebenaran (*ground truth*) di `config/taxonomy/` dan `src/domain/ontology/`.

---

## 1. Mengapa Butuh Ontologi? (Bukan Sekadar Kamus Kata)

Dalam rekrutmen, keahlian dan peran memiliki hubungan hierarkis dan implikasi logis yang terikat aturan ilmu pengetahuan:
- Seseorang yang menguasai framework tingkat tinggi seperti **FastAPI** atau **Django** secara mutlak **pasti memahami bahasa Python**, karena kedua framework tersebut ditulis dalam Python.
- Namun sebaliknya, seseorang yang baru belajar dasar bahasa **Python** belum tentu memahami cara membangun sistem production menggunakan **FastAPI**.

Hubungan satu arah yang tegas ini disebut **Implikasi Asimetris (*Asymmetric Entailment*)**. Ontologi bertindak sebagai hakim logika untuk memastikan bahwa kandidat tidak dirugikan hanya karena tidak menuliskan kata kunci generik di CV-nya.

---

## 2. Struktur Kamus Taksonomi Deklaratif (`config/taxonomy/`)

Sistem menyimpan ontologi dalam berkas YAML yang dapat dibaca manusia (*human-readable*), dipelihara tanpa perlu merombak kode program:

### A. Taksonomi Keahlian (`skills.yaml`):
Mendefinisikan ribuan teknologi, bahasa, framework, basis data, dan library:
```yaml
skill:python:
  label: Python
  type: language
  aliases:
    - python
    - python3
    - py
  related: []

skill:fastapi:
  label: FastAPI
  type: framework
  aliases:
    - fastapi
    - fast api
  broader: skill:python       # Relasi taksonomi: FastAPI berada di bawah Python

skill:postgresql:
  label: PostgreSQL
  type: database
  aliases:
    - postgresql
    - postgres
    - pgsql
  broader: skill:sql          # Menguasai PostgreSQL membuktikan kemampuan SQL
```

### B. Taksonomi Rumpun Jabatan (`role_families.yaml`):
Memetakan nama jabatan industri yang beragam ke dalam rumpun domain fungsional:
```yaml
backend:
  titles:
    - backend developer
    - back-end engineer
    - server-side engineer
    - api developer
    - golang developer
    - python developer
  domain_terms:
    - rest api
    - microservices
    - sql
    - database
    - server
  related:
    - fullstack

frontend:
  titles:
    - frontend developer
    - front-end engineer
    - ui engineer
    - react developer
  domain_terms:
    - react
    - vue
    - html5
    - tailwind
    - responsive design
  related:
    - fullstack
```

### C. Taksonomi Sertifikasi & Kepemimpinan:
- `certifications.yaml`: Memetakan lisensi profesi resmi (AWS Certified Solutions Architect, BNSP, PMP, Scrun Master).
- `leadership.yaml`: Memetakan indikator kepemimpinan (Tech Lead, Engineering Manager, Scrum Master, Mentoring).

---

## 3. Tipe Entitas & Semantik Relasi Graf

Modul `src/domain/ontology/models.py` mendefinisikan entitas graf:

```python
class EntityType(str, Enum):
    SKILL = "skill"
    ROLE = "role"
    CERTIFICATION = "certification"
    EDUCATION = "education"
    DOMAIN = "domain"

class RelationKind(str, Enum):
    IMPLIES = "implies"       # A membuktikan B (Asymmetric Entailment)
    BROADER = "broader"       # A bagian dari kategori umum B
    RELATED = "related"       # A sering digunakan bersama B (Simetris)
    SYNONYM = "synonym"       # A dan B adalah kata yang sama persis
```

### Aturan Hukum `A IMPLIES B`:
$$A \implies B \quad \cancel{\impliedby} \quad B \implies A$$
- **FastAPI $\implies$ Python:** ✅ SAH. Kandidat yang menyertakan proyek FastAPI otomatis diakui memiliki keahlian Python.
- **Python $\implies$ FastAPI:** ❌ TIDAK SAH. Mempelajari Python tidak otomatis membuktikan seseorang menguasai arsitektur async FastAPI.
- **PostgreSQL $\implies$ Relational Database / SQL:** ✅ SAH.
- **Kubernetes $\implies$ Docker / Containerization:** ✅ SAH.

---

## 4. Algoritma Penelusuran Graf (BFS Traversal & SQL CTE)

Di balik layar (`src/domain/ontology/graph.py`), pencarian hubungan tidak menggunakan LLM, melainkan **Breadth-First Search (BFS)** murni Python berkecepatan 0.001 detik:

```python
def check_entailment(candidate_concept: str, target_concept: str) -> bool:
    """Mengecek apakah candidate_concept secara sah membuktikan target_concept."""
    if candidate_concept == target_concept:
        return True
    
    queue = deque([candidate_concept])
    visited = set()
    
    while queue:
        current = queue.popleft()
        if current == target_concept:
            return True
        visited.add(current)
        
        # Telusuri edge IMPLIES dan BROADER
        for neighbor in get_outward_edges(current, kinds=["implies", "broader"]):
            if neighbor not in visited:
                queue.append(neighbor)
                
    return False
```

### Jalur Cepat (*Ontology Shortcut*):
Pada saat Graph B mengevaluasi kriteria pelamar, jika bukti kandidat dan syarat lowongan memiliki relasi langsung di graf ontologi, sistem langsung mengaktifkan bendera:  
`ONTOLOGY_SHORTCUT_EXACT = True`  
Penilaian langsung dinyatakan `STRONG` seketika **tanpa perlu membuang token dan waktu memanggil LLM luar!**

---

## 5. Bagaimana Menangani Pelamar Non-IT? (Guru, Teknik Sipil, Keuangan)

Ontologi dirancang secara modular dan dapat diperluas (*extensible*) tanpa mengotori domain inti IT:
1. **Domain Isolation:** Setiap berkas YAML mendukung pengelompokan namespace (misal: `domain:civil_engineering`, `domain:finance`, `domain:education`).
2. **Kandidat Konsep Baru (*Unmapped Concept Pool*):**  
   Jika ada pelamar yang menuliskan istilah baru di luar kamus (misal: alat ukur tanah *Total Station* atau instrumen *Teodolit*):
   - Istilah tersebut diberi label `UNKNOWN_CONCEPT:tool:total_station`.
   - Istilah ini tidak dibuang, melainkan tetap dievaluasi menggunakan **Pencarian Semantik Vektor (Harrier-270m)** dan **Penalaran Asimetris Matcher LLM**.
   - Sistem mencatat istilah tersebut ke dalam tabel saran antrean (*candidate taxonomy pool*) agar rekruter manusia dapat menyetujuinya masuk ke kamus permanen.

Dengan perpaduan ini, ontologi bertindak sebagai jangkar kepastian ilmiah yang kokoh sekaligus fleksibel menyerap perkembangan industri! 🚀
