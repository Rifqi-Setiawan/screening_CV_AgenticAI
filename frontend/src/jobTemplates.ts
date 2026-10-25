export interface JobTemplate {
  id: string
  role: string
  title: string
  location: string
  employmentType: string
  jd_text: string
}

export const ROLE_TEMPLATES: JobTemplate[] = [
  {
    id: 'backend_engineer',
    role: 'Backend Engineering',
    title: 'Senior Backend Engineer',
    location: 'Jakarta / Hybrid',
    employmentType: 'Penuh Waktu (Full-time)',
    jd_text: `Posisi: Senior Backend Engineer
Departemen: Engineering / Technology
Lokasi: Jakarta / Hybrid
Tipe: Penuh Waktu (Full-time)

Ringkasan Peran:
Kami mencari Senior Backend Engineer berpengalaman untuk merancang, membangun, dan mengoptimalkan sistem backend terdistribusi yang skalabel, aman, dan berlatensi rendah. Anda akan memimpin desain arsitektur API microservices, manajemen basis data throughput tinggi, dan keandalan sistem cloud.

Tanggung Jawab Utama:
- Merancang dan mengimplementasikan RESTful API dan gRPC services berkinerja tinggi.
- Mengelola dan mengoptimalkan database relasional (PostgreSQL) serta caching (Redis) untuk query efisien.
- Menjaga keandalan sistem, observability (logging, metrics, tracing), dan penanganan beban tinggi (high throughput).
- Menerapkan arsitektur bersih (Clean Architecture / DDD), menulis unit/integration test komprehensif, dan memandu code review tim.
- Berkolaborasi dengan engineer frontend, data, dan DevOps dalam pipeline CI/CD dan deployment Docker / Kubernetes.

Kualifikasi Wajib (Must-Have):
- Pendidikan minimal S1 atau D3 di bidang Teknik Informatika, Ilmu Komputer, Sistem Informasi, atau pengalaman kerja setara.
- Pengalaman kerja minimal 3-5 tahun sebagai Backend Developer atau Software Engineer.
- Penguasaan mendalam salah satu bahasa pemrograman backend utama: Go (Golang), Python, atau Node.js (TypeScript).
- Pemahaman kuat tentang perancangan RESTful API, database relasional (PostgreSQL / MySQL), optimasi query SQL, dan pengindeksan.

Kualifikasi Nilai Tambah (Nice-to-Have):
- Pengalaman dengan message broker / streaming data seperti Apache Kafka, RabbitMQ, atau Google Cloud Pub/Sub.
- Terbiasa dengan kontainerisasi Docker, Kubernetes, dan infrastruktur cloud (AWS, GCP, atau Azure).
- Pemahaman arsitektur Event-Driven, CQRS, dan keamanan API (OAuth2, JWT, rate limiting).`,
  },
  {
    id: 'frontend_engineer',
    role: 'Frontend Engineering',
    title: 'Frontend Engineer (React / TypeScript)',
    location: 'Jakarta / Remote',
    employmentType: 'Penuh Waktu (Full-time)',
    jd_text: `Posisi: Frontend Engineer (React / TypeScript)
Departemen: Engineering / Product
Lokasi: Jakarta / Remote
Tipe: Penuh Waktu (Full-time)

Ringkasan Peran:
Kami mencari Frontend Engineer yang berorientasi pada detail dan performa antarmuka pengguna untuk membangun antarmuka web modern yang responsif, intuitif, dan cepat. Anda akan bekerja erat dengan Product Designer (UI/UX) dan Backend Engineer untuk mewujudkan pengalaman pengguna yang mulus.

Tanggung Jawab Utama:
- Membangun Single Page Application (SPA) dan Server-Side Rendered (SSR) web apps menggunakan React, Next.js, dan TypeScript.
- Menerapkan desain UI/UX interaktif dengan Tailwind CSS, komponen desain modular, dan memastikan kepatuhan aksesibilitas web (WCAG).
- Mengintegrasikan antarmuka dengan RESTful API, WebSockets, dan mengelola state aplikasi secara efisien (Zustand, Redux Toolkit, atau TanStack Query).
- Mengoptimalkan performa Core Web Vitals, waktu rendering, dan ukuran bundel aplikasi.
- Menulis automated testing untuk frontend (Jest, React Testing Library, Playwright, atau Cypress).

Kualifikasi Wajib (Must-Have):
- Pendidikan minimal S1 atau D3 di bidang Teknik Informatika, Ilmu Komputer, Desain Komunikasi Visual, atau bidang relevan.
- Pengalaman kerja minimal 2-4 tahun dalam pengembangan antarmuka web modern.
- Penguasaan mendalam JavaScript modern (ES6+), TypeScript, dan React.js ekosistem.
- Kemahiran dalam HTML5 semantik, CSS3 modern, Responsive Web Design, dan Tailwind CSS.

Kualifikasi Nilai Tambah (Nice-to-Have):
- Pengalaman dengan Next.js App Router, SSR, dan Static Site Generation (SSG).
- Portofolio proyek frontend nyata yang dapat didemonstrasikan (GitHub repository atau live web app).
- Pengalaman dengan state management TanStack Query / React Query dan design system (shadcn/ui, Radix UI).`,
  },
  {
    id: 'data_engineer',
    role: 'Data Engineering',
    title: 'Data Platform Engineer',
    location: 'Jakarta / Hybrid',
    employmentType: 'Penuh Waktu (Full-time)',
    jd_text: `Posisi: Data Platform Engineer
Departemen: Data & Analytics
Lokasi: Jakarta / Hybrid
Tipe: Penuh Waktu (Full-time)

Ringkasan Peran:
Kami mencari Data Platform Engineer untuk membangun fondasi arsitektur data modern (Medallion Lakehouse) yang andal, scalable, dan siap pakai untuk analitik bisnis maupun machine learning. Anda akan memimpin pembangunan pipeline ekstraksi, transformasi data, dan penegakan data quality.

Tanggung Jawab Utama:
- Merancang dan memelihara pipeline data batch dan streaming dari berbagai sumber operasional ke data lake/lakehouse.
- Mengimplementasikan arsitektur Medallion (Bronze/Silver/Gold) dengan star schema dan dimensional modeling untuk analitik bisnis.
- Membangun pengujian integritas data otomatis (data quality gates / contract assertions) untuk mencegah kebocoran atau duplikasi data.
- Mengoptimalkan performa penyimpanan columnar (Apache Parquet, DuckDB, ClickHouse, atau Snowflake/BigQuery).
- Berkolaborasi dengan Data Analyst dan Data Scientist dalam menyediakan dataset analitik yang siap dikonsumsi.

Kualifikasi Wajib (Must-Have):
- Pendidikan minimal S1 atau D3 di bidang Teknik Informatika, Matematika, Statistika, Ilmu Komputer, atau Rekayasa Data.
- Pengalaman kerja minimal 2-4 tahun sebagai Data Engineer atau Analytics Engineer.
- Penguasaan tingkat lanjut bahasa pemrograman Python dan SQL (Complex analytical queries, window functions, CTE).
- Pengalaman merancang arsitektur pipeline data (ETL/ELT) dan data warehousing (Dimensional Modeling, Star Schema).

Kualifikasi Nilai Tambah (Nice-to-Have):
- Pengalaman dengan dbt (data build tool), Apache Airflow / Dagster, dan DuckDB / ClickHouse.
- Pemahaman format penyimpanan data columnar seperti Apache Parquet, Delta Lake, atau Apache Iceberg.
- Pemahaman prinsip data governance, lineage, dan pengujian kualitas data otomatis (Great Expectations / dbt test).`,
  },
  {
    id: 'civil_engineer',
    role: 'Civil Engineering',
    title: 'Civil Engineer (Struktur & Pelaksana)',
    location: 'Kediri, Jawa Timur',
    employmentType: 'Penuh Waktu (Full-time)',
    jd_text: `Posisi: Civil Engineer (Struktur & Pelaksana Proyek)
Departemen: Operasional Lapangan & Konstruksi
Lokasi: Kediri, Jawa Timur
Tipe: Penuh Waktu (Full-time)

Ringkasan Peran:
Kami mencari Civil Engineer yang berdedikasi dan memiliki integritas tinggi untuk mengawasi dan melaksanakan proyek konstruksi fasilitas olahraga, infrastruktur tanah, dan bangunan komersial. Anda bertanggung jawab memastikan mutu pekerjaan fisik, kepatuhan desain teknis, dan ketepatan jadwal di lapangan.

Tanggung Jawab Utama:
- Mengawasi pelaksanaan teknis pekerjaan konstruksi di lapangan mulai dari pembersihan lahan, pekerjaan tanah, pondasi, struktur beton, hingga finishing.
- Membaca, menganalisis, dan memvalidasi gambar kerja (Shop Drawing / As-Built Drawing) menggunakan software AutoCAD.
- Menyusun dan mengontrol Rencana Anggaran Biaya (RAB), Bill of Quantities (BoQ), dan kurva S penjadwalan proyek.
- Mengoordinasikan mandor, tenaga kerja, subkontraktor, serta opname progres fisik mingguan/bulanan.
- Menegakkan standar Keselamatan dan Kesehatan Kerja (K3 Konstruksi) dan manajemen mutu material di lingkungan kerja proyek.

Kualifikasi Wajib (Must-Have):
- Latar belakang pendidikan minimal S1 atau D3 Teknik Sipil (Civil Engineering) dari universitas terakreditasi.
- Pengalaman kerja minimal 1-3 tahun di bidang konstruksi sipil, pengawasan proyek, atau kontraktor pelaksana (Fresh graduate dengan pengalaman magang proyek dipersilakan).
- Pemahaman teknis pekerjaan tanah, pondasi, struktur beton bertulang, sistem drainase, dan finishing konstruksi.
- Kemampuan membaca gambar teknik dan mengoperasikan software AutoCAD untuk penyesuaian gambar kerja.

Kualifikasi Nilai Tambah (Nice-to-Have):
- Pengalaman dalam menyusun RAB dan kurva S jadwal menggunakan Microsoft Excel atau Microsoft Project.
- Memiliki sertifikat keahlian profesi konstruksi (SKA / SKT) atau sertifikasi K3 Konstruksi / Ahli K3 Umum.
- Pengalaman lapangan pada proyek fasilitas lapangan olahraga, gedung bertingkat, atau kolam renang.`,
  },
  {
    id: 'qa_engineer',
    role: 'Quality Assurance (QA)',
    title: 'Quality Assurance (QA) Engineer',
    location: 'Jakarta / Hybrid',
    employmentType: 'Penuh Waktu (Full-time)',
    jd_text: `Posisi: Quality Assurance (QA) Engineer
Departemen: Engineering / Quality Assurance
Lokasi: Jakarta / Hybrid
Tipe: Penuh Waktu (Full-time)

Ringkasan Peran:
Kami mencari QA Engineer yang teliti dan sistematis untuk memastikan seluruh aplikasi web, mobile, dan API memenuhi standar fungsionalitas, keamanan, dan kinerja sebelum dirilis ke produksi. Anda akan merancang test plan, mengeksekusi pengujian manual, serta membangun otomatisasi tes regresi.

Tanggung Jawab Utama:
- Menganalisis kebutuhan produk dan menyusun skenario pengujian komprehensif (Test Cases, Test Plans, Acceptance Criteria).
- Menjalankan pengujian manual dan verifikasi integritas data melalui eksekusi query database SQL.
- Mengembangkan skrip automated testing untuk API (Postman/Newman, Playwright, Pytest) dan antarmuka web.
- Melakukan pengujian System Integration Testing (SIT), End-to-End (E2E), dan regresi pada setiap siklus rilis fitur.
- Mencatat, mereproduksi, dan mengelola pelaporan defect/bug secara terstruktur di issue tracking (Jira/GitHub).

Kualifikasi Wajib (Must-Have):
- Pendidikan minimal S1 atau D3 di bidang Teknik Informatika, Sistem Informasi, Ilmu Komputer, atau bidang sains/teknik terkait.
- Pengalaman kerja minimal 1-3 tahun dalam software testing (Manual & Automated QA).
- Kemampuan menulis test case terstruktur dan melakukan pengujian fungsional RESTful API.
- Kemampuan verifikasi data menggunakan query SQL pada database relasional (PostgreSQL atau MySQL).

Kualifikasi Nilai Tambah (Nice-to-Have):
- Pengalaman menggunakan framework automation testing seperti Playwright, Cypress, Selenium, atau Pytest.
- Pemahaman alur kerja CI/CD (GitHub Actions / GitLab CI) dalam automated test execution.
- Pengalaman dalam performance testing (k6, JMeter) dan security testing dasar.`,
  },
  {
    id: 'hr_specialist',
    role: 'Human Resources',
    title: 'Talent Acquisition & HR Specialist',
    location: 'Jakarta Selatan',
    employmentType: 'Penuh Waktu (Full-time)',
    jd_text: `Posisi: Talent Acquisition & HR Specialist
Departemen: People Operations / Human Resources
Lokasi: Jakarta Selatan
Tipe: Penuh Waktu (Full-time)

Ringkasan Peran:
Kami mencari Talent Acquisition & HR Specialist yang komunikatif dan berorientasi pada pencapaian untuk memimpin siklus rekrutmen end-to-end, penarikan talenta terbaik industri, serta pengelolaan operasional sumber daya manusia yang inklusif dan berbasis data.

Tanggung Jawab Utama:
- Mengelola siklus rekrutmen end-to-end mulai dari job profiling, sourcing kandidat, screening CV, hingga penawaran kerja (Offering).
- Melakukan wawancara terstruktur berbasis kompetensi (Behavioral & Competency-based Interview) untuk menyaring kandidat potensial.
- Berkolaborasi dengan Hiring Manager lintas divisi untuk memahami profil kebutuhan posisi teknis maupun non-teknis.
- Mengelola sistem pelacak pelamar (Applicant Tracking System / ATS) dan memantau metrik rekrutmen (Time-to-Hire, Cost-per-Hire).
- Memfasilitasi proses orientasi karyawan baru (Onboarding) dan administrasi ketenagakerjaan perusahaan.

Kualifikasi Wajib (Must-Have):
- Pendidikan minimal S1 di bidang Psikologi, Manajemen Sumber Daya Manusia, Hukum, Komunikasi, atau bidang terkait.
- Pengalaman kerja minimal 2-4 tahun di bidang Talent Acquisition, Rekrutmen, atau HR Generalist (Pengalaman di agensi rekrutmen atau startup teknologi diutamakan).
- Kemampuan mendalam dalam teknik wawancara kandidat (STAR method) dan sourcing melalui platform profesional (LinkedIn Recruiter, Jobstreet).
- Keterampilan komunikasi interpersonal, negosiasi, dan manajemen pemangku kepentingan yang kuat.

Kualifikasi Nilai Tambah (Nice-to-Have):
- Pemahaman tentang Undang-Undang Ketenagakerjaan Indonesia dan administrasi hubungan industrial.
- Pengalaman menyaring posisi teknis (Software Engineering, Data, UI/UX).
- Kemampuan mengolah metrik rekrutmen menggunakan spreadsheet analitik.`,
  },
  {
    id: 'product_manager',
    role: 'Product Management',
    title: 'Product Manager (B2B SaaS / Digital)',
    location: 'Jakarta / Hybrid',
    employmentType: 'Penuh Waktu (Full-time)',
    jd_text: `Posisi: Product Manager (B2B SaaS / Digital)
Departemen: Product Management
Lokasi: Jakarta / Hybrid
Tipe: Penuh Waktu (Full-time)

Ringkasan Peran:
Kami mencari Product Manager yang strategis dan berorientasi pada solusi untuk memimpin penemuan produk, perumusan roadmap fitur, dan eksekusi sprint bersama tim engineering dan desain. Anda akan menjembatani kebutuhan pengguna, peluang bisnis, dan kelayakan teknis.

Tanggung Jawab Utama:
- Melakukan riset pengguna, wawancara pelanggan, dan analisis data pasar untuk mengidentifikasi masalah nyata dan peluang fitur baru.
- Merumuskan Product Requirements Document (PRD) yang jelas, user stories yang terperinci, dan kriteria penerimaan (Acceptance Criteria).
- Memprioritaskan backlog fitur menggunakan kerangka kerja berbasis nilai bisnis (RICE, MoSCoW, atau Value vs Effort).
- Memimpin ritual Agile/Scrum (Sprint Planning, Backlog Refinement, Standup, Retrospective) bersama tim lintas fungsi.
- Menetapkan dan memantau metrik kesuksesan produk (OKRs, Adoption Rate, Retention, Net Promoter Score).

Kualifikasi Wajib (Must-Have):
- Pendidikan minimal S1 di bidang Ilmu Komputer, Teknik Industri, Sistem Informasi, Manajemen Bisnis, atau pengalaman setara.
- Pengalaman kerja minimal 2-4 tahun sebagai Product Manager, Associate Product Manager, atau Product Owner pada produk digital.
- Kemampuan menyusun PRD, wireframe alur produk, dan user stories berstandar tinggi.
- Kemampuan analitis berbasis data kuantitatif (Product Analytics) dan pemikiran strategis yang kuat.

Kualifikasi Nilai Tambah (Nice-to-Have):
- Pengalaman mengelola produk B2B SaaS, enterprise platform, atau produk analitik/AI.
- Pengalaman menggunakan alat manajemen produk (Jira, Linear, Mixpanel, Amplitude, Figma).
- Pemahaman teknis tentang arsitektur REST API, database, dan siklus pengembangan software.`,
  },
]
