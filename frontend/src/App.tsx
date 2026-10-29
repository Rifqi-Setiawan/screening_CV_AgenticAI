import { useState, useMemo, useEffect, useRef } from 'react'
import {
  Briefcase,
  FileText,
  Upload,
  Trophy,
  Eye,
  CheckCircle2,
  AlertTriangle,
  FileCheck,
  Download,
  GitCompare,
  RotateCcw,
  Plus,
  Trash2,
  Pencil,
  ExternalLink,
  ChevronRight,
  ShieldAlert,
  Search,
  Loader2,
  Sparkles,
  X,
} from 'lucide-react'
import type { CandidateDetail, Requirement } from './types'
import { CvTextViewer, ScoreTracePanel } from './ScoreTrace'
import { ROLE_TEMPLATES } from './jobTemplates'

export default function App() {
  // Navigation & Workflow state
  const [currentStep, setCurrentStep] = useState<'setup' | 'requirements' | 'upload' | 'leaderboard'>('setup')
  const [blindMode] = useState<boolean>(true)
  
  // Job Setup state
  const [jobTitle, setJobTitle] = useState('Backend Developer - Sharing Happiness')
  const [jobLocation, setJobLocation] = useState('Jakarta / Hybrid')
  const [jobType, setJobType] = useState('Penuh Waktu (Full-time)')
  const [jobDescription, setJobDescription] = useState(
    `Sharing Happiness mencari Backend Developer yang bertanggung jawab merancang, mengembangkan, dan memelihara REST API performa tinggi, integrasi sistem pembayaran (payment gateway), manajemen basis data relasional (PostgreSQL/MySQL), serta arsitektur backend yang aman dan terukur.

Persyaratan:
- Pengalaman kerja minimal 2 tahun sebagai Backend Developer atau Software Engineer berfokus pada backend.
- Menguasai bahasa pemrograman backend seperti Golang, Python, PHP, atau Node.js.
- Menguasai perancangan REST API dan integrasi sistem.
- Mahir dalam pengelolaan basis data relasional (PostgreSQL/MySQL) dan optimasi kueri.
- Memahami clean code, unit testing, dan Git version control.`
  )

  // Requirements state (Start empty for live demo from scratch)
  const [requirements, setRequirements] = useState<Requirement[]>([])
  const [categoryWeights, setCategoryWeights] = useState<Record<string, number>>({
    EXPERIENCE: 40,
    HARD_SKILLS: 30,
    EDUCATION_CERT: 15,
    ACHIEVEMENT: 15,
  })
  const [criteriaApproved, setCriteriaApproved] = useState<boolean>(false)
  const [criteriaVersion, setCriteriaVersion] = useState<number>(0)
  const [newReqDesc, setNewReqDesc] = useState('')
  const [newReqCategory, setNewReqCategory] = useState<string>('HARD_SKILLS')
  const [newReqImportance, setNewReqImportance] = useState<string>('MUST_HAVE')
  const [newReqWeight, setNewReqWeight] = useState<number>(10)
  const [isCompiling, setIsCompiling] = useState<boolean>(false)

  // Requirement Modal Popup State
  const [editingReqIndex, setEditingReqIndex] = useState<number | null>(null)
  const [editingReqData, setEditingReqData] = useState<Requirement | null>(null)

  const handleOpenReqModal = (index: number) => {
    setEditingReqIndex(index)
    setEditingReqData({ ...requirements[index] })
  }

  const handleSaveReqModal = () => {
    if (editingReqIndex === null || !editingReqData) return
    const updated = [...requirements]
    updated[editingReqIndex] = { ...editingReqData }
    setRequirements(updated)
    setCriteriaApproved(false)
    setEditingReqIndex(null)
    setEditingReqData(null)
  }

  const handleCancelReqModal = () => {
    setEditingReqIndex(null)
    setEditingReqData(null)
  }

  // Auth & Backend sync state
  const [authToken, setAuthToken] = useState<string | null>(() => localStorage.getItem('cv_screening_token'))
  const [currentJobId, setCurrentJobId] = useState<string | null>(() => localStorage.getItem('cv_screening_job_id'))
  const [currentJobTitle, setCurrentJobTitle] = useState<string>('')
  const [currentRunId, setCurrentRunId] = useState<string | null>(null)
  const [availableJobs, setAvailableJobs] = useState<Array<{ id: string; title: string; cv_count: number }>>([])
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [isDragging, setIsDragging] = useState<boolean>(false)
  const [isUploading, setIsUploading] = useState<boolean>(false)
  const [isScreening, setIsScreening] = useState<boolean>(false)
  const [uploadStatusMsg, setUploadStatusMsg] = useState<string>('')
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false)
  const pollTimerRef = useRef<any>(null)
  const isPollingRef = useRef<boolean>(false)

  // Uploaded files list
  const [uploadedFiles, setUploadedFiles] = useState<Array<{ id?: string; name: string; size: string; status: 'ready' | 'processing' | 'review' | 'unqualified' | 'duplicate'; reason?: string }>>([])

  // Candidates & Leaderboard state
  const [candidates, setCandidates] = useState<CandidateDetail[]>([])
  const [activeBand, setActiveBand] = useState<'ALL' | 'A' | 'B' | 'C' | 'MANUAL'>('ALL')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCandidate, setSelectedCandidate] = useState<CandidateDetail | null>(null)
  const [selectedForCompare, setSelectedForCompare] = useState<string[]>([])
  const [isCompareOpen, setIsCompareOpen] = useState(false)
  const [isExportOpen, setIsExportOpen] = useState(false)
  const [activeDrawerTab, setActiveDrawerTab] = useState<'ringkasan' | 'jejak' | 'kartu_skor' | 'cv_asli' | 'riwayat'>('ringkasan')
  const [selectedQuoteToHighlight, setSelectedQuoteToHighlight] = useState<string | null>(null)
  const [selectedAtomKey, setSelectedAtomKey] = useState<string | null>(null)

  // Policy Linter for prohibited criteria (physical appearance only; religion & gender are permitted)
  const prohibitedFlags = useMemo(() => {
    const flags: string[] = []
    requirements.forEach((r) => {
      const txt = (r.description + ' ' + (r.source_text || '')).toLowerCase()
      if (/menarik|penampilan|good looking|foto\s+full\s+body|proporsional/.test(txt)) {
        flags.push(`Kriteria penampilan fisik (${r.requirement_id}): Tidak boleh digunakan`)
      }
    })
    return flags
  }, [requirements])

  // Dynamic sum of category weights
  const totalCategoryWeight = useMemo(() => {
    return (
      Number(categoryWeights.EXPERIENCE || 0) +
      Number(categoryWeights.HARD_SKILLS || 0) +
      Number(categoryWeights.EDUCATION_CERT || 0) +
      Number(categoryWeights.ACHIEVEMENT || 0)
    )
  }, [categoryWeights])

  // Filtered candidates for leaderboard
  const filteredCandidates = useMemo(() => {
    return candidates.filter((c) => {
      if (activeBand !== 'ALL') {
        if (activeBand === 'A' && c.band !== 'A') return false
        if (activeBand === 'B' && c.band !== 'B') return false
        if (activeBand === 'C' && c.band !== 'C') return false
        if (activeBand === 'MANUAL' && c.recommendation !== 'MANUAL_CHECK' && c.recommendation !== 'REJECTED_NOT_A_CV') return false
      }
      if (searchQuery) {
        const q = searchQuery.toLowerCase()
        const nameMatch = (blindMode && !c.revealed ? c.blind_id : c.real_name).toLowerCase().includes(q)
        const fileMatch = c.file_name.toLowerCase().includes(q)
        if (!nameMatch && !fileMatch) return false
      }
      return true
    })
  }, [candidates, activeBand, searchQuery, blindMode])

  const getAuthHeaders = (): Record<string, string> => {
    const t = authToken || localStorage.getItem('cv_screening_token')
    return t ? { Authorization: `Bearer ${t}` } : {}
  }

  // Auto-login recruiter on mount & handle token refresh
  const loginRecruiter = async (): Promise<string | null> => {
    try {
      const res = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: 'recruiter@rifqisetiawan.my.id',
          password: 'RecruiterPassword2026!',
        }),
      })
      if (res.ok) {
        const data = await res.json()
        if (data.access_token) {
          setAuthToken(data.access_token)
          localStorage.setItem('cv_screening_token', data.access_token)
          return data.access_token
        }
      }
    } catch (e) {
      console.warn('Auto-login error:', e)
    }
    return null
  }

  const selectJob = async (jId: string, title?: string) => {
    setCurrentJobId(jId)
    localStorage.setItem('cv_screening_job_id', jId)
    if (title) {
      setJobTitle(title)
      setCurrentJobTitle(title)
    }

    try {
      // 1. Fetch full job details (including jd_text, location, employment_type)
      const res = await fetch(`/api/v1/jobs/${jId}`, { headers: { ...getAuthHeaders() } })
      if (res.ok) {
        const data = await res.json()
        if (data.title) {
          setJobTitle(data.title)
          setCurrentJobTitle(data.title)
        }
        if (data.jd_text) {
          setJobDescription(data.jd_text)
        }
        if (data.location) {
          setJobLocation(data.location)
        }
        if (data.employment_type) {
          setJobType(data.employment_type)
        }
      }

      // 2. Fetch requirements if already created for this job
      const resReq = await fetch(`/api/v1/jobs/${jId}/requirements`, { headers: { ...getAuthHeaders() } })
      if (resReq.ok) {
        const reqList = await resReq.json()
        const catWeightsHdr = resReq.headers.get('X-Category-Weights')
        const verHdr = resReq.headers.get('X-Requirements-Version')
        if (catWeightsHdr) {
          try {
            const parsedWeights = JSON.parse(catWeightsHdr)
            if (parsedWeights && typeof parsedWeights === 'object') {
              setCategoryWeights(parsedWeights)
            }
          } catch (e) {
            console.warn('Failed parsing category weights header:', e)
          }
        }
        if (verHdr) {
          setCriteriaVersion(parseInt(verHdr) || 1)
        }
        if (Array.isArray(reqList) && reqList.length > 0) {
          setRequirements(reqList)
          setCriteriaApproved(true)
        } else {
          setCriteriaApproved(false)
        }
      }
    } catch (e) {
      console.warn('Error fetching job details:', e)
    }

    await fetchJobCvsStatus(jId)
    await fetchLatestLeaderboard(jId)
  }

  const fetchJobsList = async () => {
    try {
      const res = await fetch('/api/v1/jobs', { headers: { ...getAuthHeaders() } })
      if (res.ok) {
        const jobs = await res.json()
        if (Array.isArray(jobs) && jobs.length > 0) {
          setAvailableJobs(jobs.map((j: any) => ({ id: j.id, title: j.title, cv_count: j.cv_count || 0 })))

          const savedId = localStorage.getItem('cv_screening_job_id')
          const found = jobs.find((j: any) => j.id === savedId)
          if (found) {
            await selectJob(found.id, found.title)
          } else {
            const bestJob = jobs.slice().sort((a: any, b: any) => (b.cv_count || 0) - (a.cv_count || 0))[0]
            if (bestJob) {
              await selectJob(bestJob.id, bestJob.title)
            }
          }
        }
      }
    } catch (e) {
      console.warn('Error fetching jobs:', e)
    }
  }

  const handleRenameJob = async () => {
    if (!currentJobId) return
    const newTitle = window.prompt('Ubah nama lowongan:', currentJobTitle || jobTitle)
    if (!newTitle || !newTitle.trim() || newTitle.trim() === (currentJobTitle || jobTitle)) return
    try {
      const res = await fetch(`/api/v1/jobs/${currentJobId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(),
        },
        body: JSON.stringify({ title: newTitle.trim() }),
      })
      if (res.ok) {
        const updated = await res.json()
        setJobTitle(updated.title)
        setCurrentJobTitle(updated.title)
        setAvailableJobs((prev) =>
          prev.map((j) => (j.id === currentJobId ? { ...j, title: updated.title } : j))
        )
      } else {
        alert('Gagal mengubah nama lowongan.')
      }
    } catch (e) {
      console.error(e)
      alert('Terjadi kesalahan jaringan saat mengubah nama lowongan.')
    }
  }

  const handleDeleteJob = async () => {
    if (!currentJobId) return
    const title = currentJobTitle || jobTitle || 'Lowongan ini'
    const confirmed = window.confirm(
      `Hapus lowongan "${title}"?\n\nSemua berkas CV dan hasil evaluasi lowongan ini akan dihapus permanen.`
    )
    if (!confirmed) return
    try {
      const res = await fetch(`/api/v1/jobs/${currentJobId}`, {
        method: 'DELETE',
        headers: {
          ...getAuthHeaders(),
        },
      })
      if (res.ok) {
        const remaining = availableJobs.filter((j) => j.id !== currentJobId)
        setAvailableJobs(remaining)
        if (remaining.length > 0) {
          await selectJob(remaining[0].id, remaining[0].title)
        } else {
          setCurrentJobId('')
          setCurrentJobTitle('')
          setJobTitle('')
          setJobDescription('')
          setJobLocation('')
          setRequirements([])
          setUploadedFiles([])
          setCandidates([])
          setCriteriaApproved(false)
          setCurrentStep('setup')
        }
      } else {
        alert('Gagal menghapus lowongan.')
      }
    } catch (e) {
      console.error(e)
      alert('Terjadi kesalahan jaringan saat menghapus lowongan.')
    }
  }

  useEffect(() => {
    const init = async () => {
      await loginRecruiter()
      await fetchJobsList()
    }
    init()
  }, [])

  const ensureJobExists = async (): Promise<string> => {
    if (currentJobId) return currentJobId
    try {
      const listRes = await fetch('/api/v1/jobs', { headers: { ...getAuthHeaders() } })
      if (listRes.ok) {
        const jobs = await listRes.json()
        if (jobs && jobs.length > 0) {
          const bestJob = jobs.slice().sort((a: any, b: any) => (b.cv_count || 0) - (a.cv_count || 0))[0]
          const jId = bestJob.id
          await selectJob(jId, bestJob.title)
          return jId
        }
      }
    } catch (e) {
      console.warn('Job listing error:', e)
    }
    try {
      const res = await fetch('/api/v1/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({
          title: jobTitle,
          jd_text: jobDescription,
          location: jobLocation,
          employment_type: jobType,
          external_ref: 'JD-WEB',
        }),
      })
      if (res.ok) {
        const data = await res.json()
        const jId = data.id
        await selectJob(jId, jobTitle)
        return jId
      }
    } catch (e) {
      console.warn('Job creation error:', e)
    }
    return '5364833c-ae8a-4b11-aeff-016b34903da0'
  }

  const stopPollingJobCvs = () => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current)
      pollTimerRef.current = null
    }
    isPollingRef.current = false
  }

  const startPollingJobCvs = (jId: string) => {
    if (!jId) return
    stopPollingJobCvs()
    isPollingRef.current = true
    let attempts = 0
    const maxAttempts = 150 // Poll up to 5 minutes (150 * 2000ms)

    const tick = async () => {
      attempts++
      const allDone = await fetchJobCvsStatus(jId)
      if (allDone || attempts >= maxAttempts) {
        stopPollingJobCvs()
      }
    }

    tick()
    pollTimerRef.current = setInterval(tick, 2000)
  }

  const fetchJobCvsStatus = async (jId: string): Promise<boolean> => {
    if (!jId) return true
    try {
      const res = await fetch(`/api/v1/jobs/${jId}/cvs/status`, {
        headers: { ...getAuthHeaders() },
      })
      if (res.ok) {
        const data = await res.json()
        const rawDocs = data.documents || data.files || []
        if (Array.isArray(rawDocs) && rawDocs.length > 0) {
          const mapped = rawDocs.map((f: any) => ({
            id: f.id,
            name: f.filename,
            size: f.size_bytes ? `${Math.round(f.size_bytes / 1024)} KB` : 'Terproses',
            status:
              f.status === 'READY'
                ? ('ready' as const)
                : f.status === 'NEEDS_REVIEW'
                ? ('review' as const)
                : f.status === 'DUPLICATE'
                ? ('duplicate' as const)
                : f.status === 'PROCESSING' || f.status === 'RECEIVED'
                ? ('processing' as const)
                : ('unqualified' as const),
            reason:
              f.duplicate_of
                ? `Duplikat dari: ${f.duplicate_of}`
                : f.status === 'DUPLICATE'
                ? 'Berkas duplikat identik (sudah diunggah sebelumnya)'
                : f.reasons && f.reasons.length > 0
                ? f.reasons.join(', ')
                : f.flags && f.flags.length > 0
                ? f.flags.join(', ')
                : f.status === 'PROCESSING' || f.status === 'RECEIVED'
                ? 'Sedang diekstrak dan dianalisis oleh server...'
                : 'Ekstraksi identitas & keahlian terverifikasi',
          }))
          setUploadedFiles(mapped)
          const allDone = rawDocs.every((f: any) => f.status !== 'RECEIVED' && f.status !== 'PROCESSING')
          return allDone
        } else if (Array.isArray(rawDocs) && rawDocs.length === 0) {
          return true
        }
      }
    } catch (e) {
      console.warn('Error polling status:', e)
      return false
    }
    return false
  }

  const handleManualRefresh = async () => {
    if (!currentJobId) return
    setIsRefreshing(true)
    const allDone = await fetchJobCvsStatus(currentJobId)
    if (!allDone) {
      startPollingJobCvs(currentJobId)
    }
    setTimeout(() => setIsRefreshing(false), 500)
  }

  const handleUploadFiles = async (files: FileList | File[]) => {
    if (!files || files.length === 0) return
    setIsUploading(true)
    setUploadStatusMsg(`Mengunggah ${files.length} berkas CV...`)

    // Instantly show the selected files in the table as 'processing'
    const immediateItems = Array.from(files).map((f) => ({
      name: f.name,
      size: `${Math.round(f.size / 1024)} KB`,
      status: 'processing' as const,
      reason: 'Sedang mengunggah dan menganalisis berkas di server...',
    }))
    setUploadedFiles((prev) => [
      ...immediateItems,
      ...prev.filter((p) => !immediateItems.some((n) => n.name === p.name)),
    ])

    try {
      const jId = await ensureJobExists()
      const formData = new FormData()
      for (let i = 0; i < files.length; i++) {
        formData.append('files', files[i])
      }
      let currentHeaders = getAuthHeaders()
      let res = await fetch(`/api/v1/jobs/${jId}/cvs`, {
        method: 'POST',
        headers: { ...currentHeaders },
        body: formData,
      })

      // Automatic recovery if token is expired or unauthorized
      if (res.status === 401) {
        console.warn('Token expired or unauthorized, auto-refreshing token...')
        localStorage.removeItem('cv_screening_token')
        const freshToken = await loginRecruiter()
        if (freshToken) {
          res = await fetch(`/api/v1/jobs/${jId}/cvs`, {
            method: 'POST',
            headers: { Authorization: `Bearer ${freshToken}` },
            body: formData,
          })
        }
      }

      if (res.ok) {
        const resData = await res.json().catch(() => null)
        // If server unpacked archive entries, immediately update table with extracted files
        if (resData && Array.isArray(resData.files) && resData.files.length > 0) {
          setUploadedFiles(
            resData.files.map((f: any) => ({
              name: f.filename,
              size: 'Memproses...',
              status: f.status === 'DUPLICATE' ? ('duplicate' as const) : ('processing' as const),
              reason:
                f.status === 'DUPLICATE'
                  ? 'Berkas duplikat identik (sudah diunggah sebelumnya)'
                  : 'Sedang diekstrak dan dianalisis oleh server...',
            }))
          )
        }
        setUploadStatusMsg('Unggahan diterima server. Mengekstrak dan menganalisis berkas...')
        // Start continuous background polling
        startPollingJobCvs(jId)
      } else {
        const err = await res.json().catch(() => ({}))
        const msg = err.detail || err.message || res.statusText || `Server error (${res.status})`
        alert(`Gagal mengunggah berkas: ${msg}`)
        setUploadedFiles((prev) =>
          prev.map((p) =>
            immediateItems.some((imm) => imm.name === p.name)
              ? { ...p, status: 'unqualified' as const, reason: `Gagal diunggah: ${msg}` }
              : p
          )
        )
      }
    } catch (e: any) {
      alert(`Terjadi kesalahan jaringan: ${e.message}`)
      setUploadedFiles((prev) =>
        prev.map((p) =>
          immediateItems.some((imm) => imm.name === p.name)
            ? { ...p, status: 'unqualified' as const, reason: `Kesalahan jaringan: ${e.message}` }
            : p
        )
      )
    } finally {
      setIsUploading(false)
      setUploadStatusMsg('')
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleLoadSampleCvs = () => {
    setUploadedFiles([
      { name: 'S1_senior_backend_id.pdf', size: '142 KB', status: 'ready', reason: 'Ekstraksi identitas & keahlian terverifikasi' },
      { name: 'S2_backend_fintech_en.pdf', size: '128 KB', status: 'ready', reason: 'Ekstraksi identitas & keahlian terverifikasi' },
      { name: 'S3_backend_mixed_lang.pdf', size: '156 KB', status: 'ready', reason: 'Ekstraksi identitas & keahlian terverifikasi' },
      { name: 'S4_lead_backend_two_column.pdf', size: '185 KB', status: 'ready', reason: 'Ekstraksi identitas & keahlian terverifikasi' },
      { name: 'S5_backend_healthtech_id.docx', size: '112 KB', status: 'ready', reason: 'Ekstraksi identitas & keahlian terverifikasi' },
      { name: 'M1_nodejs_backend_two_column.pdf', size: '139 KB', status: 'ready', reason: 'Ekstraksi identitas & keahlian terverifikasi' },
      { name: 'M2_data_analyst_id.pdf', size: '145 KB', status: 'ready', reason: 'Ekstraksi identitas & keahlian terverifikasi' },
      { name: 'M3_fresh_graduate_scan_id.pdf', size: '210 KB', status: 'ready', reason: 'Ekstraksi identitas & keahlian terverifikasi' },
      { name: 'M4_qa_automation_en.docx', size: '98 KB', status: 'ready', reason: 'Ekstraksi identitas & keahlian terverifikasi' },
      { name: 'M5_php_fullstack_two_column_id.pdf', size: '140 KB', status: 'ready', reason: 'Ekstraksi identitas & keahlian terverifikasi' },
      { name: 'I1_hr_generalist_id.pdf', size: '115 KB', status: 'ready', reason: 'Ekstraksi identitas & keahlian terverifikasi' },
      { name: 'E1_empty_cv.pdf', size: '12 KB', status: 'review', reason: 'Dokumen kosong / konten tidak memadai' },
      { name: 'E3_hidden_prompt_injection.pdf', size: '160 KB', status: 'ready', reason: 'Teks tersembunyi dinetralkan' },
      { name: 'E6_password_protected.pdf', size: '84 KB', status: 'unqualified', reason: 'PDF terkunci password — minta kandidat kirim ulang' },
      { name: 'E8_duplicate_of_S1.pdf', size: '142 KB', status: 'duplicate', reason: 'Duplikat identik dari S1_senior_backend_id.pdf' },
    ])
  }

  const handleClearUploadedCvs = async () => {
    if (!confirm('Apakah Anda yakin ingin mengosongkan semua berkas CV yang telah diunggah untuk lowongan ini?')) return
    try {
      const jId = await ensureJobExists()
      const res = await fetch(`/api/v1/jobs/${jId}/cvs`, {
        method: 'DELETE',
        headers: { ...getAuthHeaders() },
      })
      if (res.ok) {
        setUploadedFiles([])
        setCandidates([])
        setCurrentRunId(null)
        setSelectedCandidate(null)
      } else {
        alert('Gagal mengosongkan berkas CV dari server.')
      }
    } catch (e: any) {
      alert(`Terjadi kesalahan: ${e.message}`)
    }
  }

  const handleDeleteSingleCv = async (docId?: string, fileName?: string) => {
    if (!docId) return
    const confirmed = window.confirm(`Apakah Anda yakin ingin menghapus berkas "${fileName || 'ini'}" dari perankingan?`)
    if (!confirmed) return
    try {
      const jId = currentJobId || (await ensureJobExists())
      const res = await fetch(`/api/v1/jobs/${jId}/cvs/${docId}`, {
        method: 'DELETE',
        headers: { ...getAuthHeaders() },
      })
      if (res.ok) {
        setUploadedFiles((prev) => prev.filter((f) => f.id !== docId))
        if (currentRunId && currentJobId) {
          fetchLatestLeaderboard(currentJobId, 1)
        }
      } else {
        alert('Gagal menghapus berkas CV dari server.')
      }
    } catch (e) {
      console.warn('Error deleting single CV:', e)
      alert('Gagal menghubungi server saat menghapus berkas.')
    }
  }

  const handleRetrySingleCv = async (docId?: string) => {
    if (!docId) return
    try {
      const jId = currentJobId || (await ensureJobExists())
      const res = await fetch(`/api/v1/jobs/${jId}/cvs/${docId}/retry`, {
        method: 'POST',
        headers: { ...getAuthHeaders() },
      })
      if (res.ok) {
        setUploadedFiles((prev) =>
          prev.map((f) =>
            f.id === docId
              ? { ...f, status: 'processing', reason: 'Sedang diproses ulang oleh sistem...' }
              : f
          )
        )
        startPollingJobCvs(jId)
      } else {
        alert('Gagal menjadwalkan proses ulang berkas.')
      }
    } catch (e) {
      console.warn('Error retrying single CV:', e)
    }
  }

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleUploadFiles(e.dataTransfer.files)
    }
  }

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleUploadFiles(e.target.files)
    }
  }

  const fetchLatestLeaderboard = async (jId?: string, maxAttempts = 6) => {
    try {
      const targetJobId = jId || (await ensureJobExists())
      if (!targetJobId) return
      for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        const res = await fetch(`/api/v1/jobs/${targetJobId}/screenings/latest`, {
          headers: { ...getAuthHeaders() },
        })
        if (res.ok) {
          const data = await res.json()
          if (data.latest_run && data.rankings && data.rankings.length > 0) {
            setCurrentRunId(data.screening_run_id || data.latest_run.id)
            const mappedCandidates: CandidateDetail[] = data.rankings.map((r: any, idx: number) => ({
              rank: r.rank || idx + 1,
              cv_id: r.cv_id || r.candidate_id,
              file_name: r.file_name,
              blind_id: `C-${String(idx + 1).padStart(4, '0')}`,
              real_name: r.file_name.replace(/\.[^/.]+$/, '').replace(/_/g, ' '),
              revealed: false,
              final_score: typeof r.final_score === 'number' ? r.final_score : parseFloat(r.final_score) || 0,
              raw_score: typeof r.raw_score === 'number' ? r.raw_score : parseFloat(r.raw_score) || 0,
              band: r.band,
              recommendation: r.recommendation,
              category_breakdown: r.category_breakdown || {},
              metrics: {},
              flags: r.flags || [],
              quality_status: r.quality_status || 'READY',
              eligibility_status: r.eligibility_status || 'ELIGIBLE',
              eligibility_reasons: r.eligibility_reasons || [],
              requirement_states: r.requirement_states || {},
              evidence: {},
              explanation: {
                band: r.band,
                recommendation: r.recommendation,
                final_score: typeof r.final_score === 'number' ? r.final_score : parseFloat(r.final_score) || 0,
                strengths: [],
                unproven: [],
                interview_questions: [],
              },
              full_text: `Dokumen: ${r.file_name}\nStatus Ingestion: ${r.quality_status || 'READY'}\nSkor Evaluasi: ${r.final_score}`,
            }))
            setCandidates(mappedCandidates)
            return
          }
        }
        if (attempt < maxAttempts) {
          await new Promise((resolve) => setTimeout(resolve, 1000))
        }
      }
    } catch (e) {
      console.warn('Error fetching latest leaderboard:', e)
    }
  }

  useEffect(() => {
    if (currentStep === 'upload' && currentJobId) {
      fetchJobCvsStatus(currentJobId).then((allDone) => {
        if (!allDone) {
          startPollingJobCvs(currentJobId)
        }
      })
    } else if (currentStep === 'leaderboard') {
      fetchLatestLeaderboard()
    }
  }, [currentStep, currentJobId])

  useEffect(() => {
    return () => {
      stopPollingJobCvs()
    }
  }, [])

  const handleStartScreening = async () => {
    setIsScreening(true)
    try {
      const jId = await ensureJobExists()
      // Import approved criteria to backend
      try {
        await fetch(`/api/v1/jobs/${jId}/requirements/import-approved`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
          body: JSON.stringify({
            requirement_set_version: criteriaVersion,
            category_weights: categoryWeights,
            requirements: requirements,
            status: 'DRAFT',
          }),
        })
        // Formally approve the requirement set via the approval gate endpoint (FX-03)
        await fetch(`/api/v1/jobs/${jId}/requirements/approve`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        })
      } catch (e) {
        console.warn('Requirements import note:', e)
      }

      // Trigger screening run synchronously for immediate completion
      const res = await fetch(`/api/v1/jobs/${jId}/screenings?sync=true`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({ use_verifier: false }),
      })

      if (res.status === 409) {
        const errJson = await res.json().catch(() => ({}))
        alert(errJson.detail || 'Kriteria belum disetujui. Silakan setujui kriteria lowongan terlebih dahulu.')
        setCurrentStep('requirements')
        return
      }

      if (res.ok) {
        const data = await res.json()
        const runId = data.screening_run_id || data.run_id
        setCurrentRunId(runId)
        await fetchLatestLeaderboard(jId)
        setCurrentStep('leaderboard')
      } else {
        const errJson = await res.json().catch(() => ({}))
        alert(`Gagal menjalankan evaluasi: ${errJson.detail || res.statusText || 'Terjadi kesalahan pada server'}`)
      }
    } catch (e: any) {
      console.warn('Error starting screening:', e)
      alert(`Terjadi kesalahan: ${e.message}`)
    } finally {
      setIsScreening(false)
    }
  }

  const handleSelectCandidate = async (cand: CandidateDetail) => {
    setSelectedCandidate(cand)
    setActiveDrawerTab('ringkasan')
    setSelectedAtomKey(null)
    setSelectedQuoteToHighlight(null)
    if (currentJobId && currentRunId) {
      try {
        const res = await fetch(`/api/v1/jobs/${currentJobId}/screenings/${currentRunId}/candidates/${cand.cv_id}`, {
          headers: { ...getAuthHeaders() },
        })
        if (res.ok) {
          const detail = await res.json()
          setSelectedCandidate((prev) => {
            if (!prev) return null
            return {
              ...prev,
              requirement_states: detail.requirement_states || prev.requirement_states,
              evidence: detail.evidence || prev.evidence,
              explanation: detail.explanation || prev.explanation,
              category_breakdown: detail.category_breakdown || prev.category_breakdown,
              flags: detail.flags || prev.flags,
              score_trace: detail.score_trace ?? prev.score_trace,
              full_text: detail.full_text ?? prev.full_text,
              source_highlights: detail.source_highlights ?? prev.source_highlights,
            }
          })
        }
      } catch (e) {
        console.warn('Candidate detail fetch note:', e)
      }
    }
  }

  // Handlers
  const handleRevealCandidate = async (cv_id: string) => {
    const confirmed = window.confirm(
      'Membuka identitas kandidat ini akan dicatat dalam Audit Trail resmi. Apakah Anda yakin ingin membuka identitas?'
    )
    if (confirmed) {
      let revealedName = ''
      try {
        const res = await fetch(`/api/v1/candidates/${cv_id}/reveal-identity`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
          body: JSON.stringify({ reason: 'Audit identitas pelamar resmi di UI' }),
        })
        if (res.ok) {
          const data = await res.json()
          revealedName = data.full_name || ''
        }
      } catch (e) {
        console.warn('Reveal API note:', e)
      }

      setCandidates((prev) =>
        prev.map((c) =>
          c.cv_id === cv_id
            ? { ...c, revealed: true, real_name: revealedName || c.real_name }
            : c
        )
      )
      if (selectedCandidate && selectedCandidate.cv_id === cv_id) {
        setSelectedCandidate((prev) =>
          prev ? { ...prev, revealed: true, real_name: revealedName || prev.real_name } : null
        )
      }
    }
  }

  const handleDecision = (cv_id: string, decision: 'SHORTLIST' | 'HOLD' | 'TIDAK_LANJUT', note: string = '') => {
    setCandidates((prev) =>
      prev.map((c) => (c.cv_id === cv_id ? { ...c, decision, decision_notes: note } : c))
    )
    if (selectedCandidate && selectedCandidate.cv_id === cv_id) {
      setSelectedCandidate((prev) => (prev ? { ...prev, decision, decision_notes: note } : null))
    }
  }

  const handleAddRequirement = () => {
    if (!newReqDesc.trim()) return
    const newId = `R${requirements.length + 1}`
    const newReq: Requirement = {
      requirement_id: newId,
      description: newReqDesc,
      category: newReqCategory,
      kind: newReqCategory === 'EXPERIENCE' ? 'EXPERIENCE_DURATION' : newReqCategory === 'EDUCATION_CERT' ? 'EDUCATION' : 'SKILL',
      importance: newReqImportance,
      weight: newReqWeight,
      concepts: [],
      source_text: 'Ditambahkan secara manual oleh recruiter',
    }
    setRequirements([...requirements, newReq])
    setNewReqDesc('')
    setCriteriaApproved(false)
  }

  const handleCompileFromJd = async () => {
    if (!jobDescription.trim()) {
      alert('Silakan masukkan deskripsi lowongan terlebih dahulu.')
      return
    }
    setIsCompiling(true)

    // Ensure new or updated job is created in backend
    try {
      if (!currentJobId || (currentJobTitle && currentJobTitle !== jobTitle)) {
        const createRes = await fetch('/api/v1/jobs', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
          body: JSON.stringify({
            title: jobTitle || 'Lowongan Baru',
            jd_text: jobDescription,
            location: jobLocation || 'Indonesia',
            employment_type: jobType || 'full_time',
            external_ref: `JD-${Date.now().toString().slice(-6)}`,
          }),
        })
        if (createRes.ok) {
          const newJob = await createRes.json()
          setCurrentJobId(newJob.id)
          setCurrentJobTitle(newJob.title)
          localStorage.setItem('cv_screening_job_id', newJob.id)
          setAvailableJobs((prev) => [
            { id: newJob.id, title: newJob.title, cv_count: 0 },
            ...prev.filter((j) => j.id !== newJob.id),
          ])
          setUploadedFiles([])
          setCandidates([])
        }
      }
    } catch (e) {
      console.warn('Job create error during compile:', e)
    }

    try {
      const res = await fetch('/api/v1/requirements/compile-preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({ jd_text: jobDescription }),
      })
      if (res.ok) {
        const data = await res.json()
        if (data.requirements && Array.isArray(data.requirements) && data.requirements.length > 0) {
          setRequirements(data.requirements)
          if (data.category_weights && typeof data.category_weights === 'object') {
            setCategoryWeights(data.category_weights)
          }
          setCriteriaVersion(1)
          setCriteriaApproved(false)
          setCurrentStep('requirements')
          return
        }
      }
    } catch (err) {
      console.warn('Backend compiler API not reachable, using fallback:', err)
    } finally {
      setIsCompiling(false)
    }

    // Client-side parser fallback
    const lines = jobDescription
      .split('\n')
      .map((l) => l.trim().replace(/^[-*•0-9.)]\s*/, ''))
      .filter((l) => l.length >= 8 && !l.startsWith('#'))

    if (lines.length > 0) {
      const extracted: Requirement[] = lines.slice(0, 12).map((l, idx) => {
        const lower = l.toLowerCase()
        const isExp =
          idx === 0 ||
          lower.includes('tahun') ||
          lower.includes('pengalaman') ||
          lower.includes('tanggung jawab')
        const isEdu =
          lower.includes('pendidikan') ||
          lower.includes('s1') ||
          lower.includes('d3') ||
          lower.includes('sertifikasi')
        return {
          requirement_id: `R${idx + 1}`,
          description: l,
          category: isExp
            ? 'EXPERIENCE'
            : isEdu
            ? 'EDUCATION_CERT'
            : 'HARD_SKILLS',
          kind: isExp
            ? 'EXPERIENCE_DURATION'
            : isEdu
            ? 'EDUCATION'
            : 'SKILL',
          importance:
            idx < 2
              ? 'MUST_HAVE'
              : idx < 5
              ? 'STRONG_PREFERENCE'
              : 'NICE_TO_HAVE',
          weight: idx < 2 ? 20 : 10,
          concepts: [],
          source_text: l,
        }
      })
      setRequirements(extracted)
      setCriteriaVersion(1)
      setCriteriaApproved(false)
      setCurrentStep('requirements')
    } else {
      setCurrentStep('requirements')
    }
  }

  const handleApproveCriteria = async () => {
    if (prohibitedFlags.length > 0) {
      alert('Terdapat kriteria diskriminatif terlarang! Harap hapus kriteria tersebut sebelum menyetujui.')
      return
    }
    if (totalCategoryWeight !== 100) {
      if (!confirm(`Total distribusi bobot kategori saat ini ${totalCategoryWeight}% (bukan 100%). Tetap lanjutkan dan kunci versi kriteria ini?`)) {
        return
      }
    }
    setCriteriaApproved(true)
    const nextVer = criteriaVersion + 1
    setCriteriaVersion(nextVer)

    // Automatically persist approved requirements and custom category weights to backend
    if (currentJobId) {
      try {
        await fetch(`/api/v1/jobs/${currentJobId}/requirements/import-approved`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
          body: JSON.stringify({
            requirement_set_version: nextVer,
            category_weights: categoryWeights,
            requirements: requirements,
            status: 'DRAFT',
          }),
        })
        await fetch(`/api/v1/jobs/${currentJobId}/requirements/approve`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        })
      } catch (e) {
        console.warn('Requirements persist error:', e)
      }
    }
    alert(`Kriteria lowongan dan bobot penilaian berhasil disetujui dan dikunci (Versi ${nextVer}).`)
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-800 flex flex-col font-sans">
      {/* Top Application Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30 px-6 py-2.5 flex flex-wrap items-center justify-between gap-4 shadow-xs">
        {/* Left Section: Brand & Active Job Context */}
        <div className="flex items-center space-x-3.5">
          {/* Brand Logo & Name */}
          <div className="flex items-center space-x-2.5">
            <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-indigo-700 to-indigo-500 flex items-center justify-center text-white font-extrabold text-sm shadow-xs tracking-wider">
              CV
            </div>
            <div className="flex items-center space-x-2">
              <span className="text-sm font-bold text-slate-900 tracking-tight">AI CV Screening</span>
              <span className="text-[10px] font-semibold text-indigo-700 bg-indigo-50 border border-indigo-200/80 px-1.5 py-0.5 rounded-md">
                v2.1
              </span>
            </div>
          </div>

          <div className="h-5 w-px bg-slate-200 hidden sm:block" />

          {/* Job Selector & Actions */}
          {availableJobs.length > 0 ? (
            <div className="flex items-center space-x-1.5 bg-slate-50 border border-slate-200/90 rounded-lg p-1 shadow-2xs">
              <div className="flex items-center pl-1.5 pr-1 space-x-1 text-slate-500 text-xs">
                <Briefcase className="w-3.5 h-3.5 text-indigo-600 shrink-0" />
                <span className="font-medium text-slate-600 hidden md:inline">Lowongan:</span>
              </div>
              <select
                value={currentJobId || ''}
                onChange={(e) => {
                  const selected = availableJobs.find((j) => j.id === e.target.value)
                  if (selected) selectJob(selected.id, selected.title)
                }}
                className="text-xs bg-white border border-slate-200 font-semibold text-slate-800 rounded-md px-2.5 py-1 focus:outline-none focus:ring-1 focus:ring-indigo-500 min-w-[170px] max-w-[260px] lg:max-w-[340px] truncate shadow-2xs transition-colors cursor-pointer"
              >
                {availableJobs.map((j) => (
                  <option key={j.id} value={j.id}>
                    {j.title}
                  </option>
                ))}
              </select>
              <div className="flex items-center space-x-1">
                <button
                  type="button"
                  onClick={handleRenameJob}
                  disabled={!currentJobId}
                  className="h-6.5 w-6.5 inline-flex items-center justify-center text-slate-500 hover:text-indigo-600 bg-white hover:bg-indigo-50/70 rounded-md border border-slate-200 hover:border-indigo-300 transition-all disabled:opacity-30 disabled:cursor-not-allowed shadow-2xs"
                  title="Ubah Nama Lowongan (Rename)"
                >
                  <Pencil className="w-3 h-3" />
                </button>
                <button
                  type="button"
                  onClick={handleDeleteJob}
                  disabled={!currentJobId}
                  className="h-6.5 w-6.5 inline-flex items-center justify-center text-slate-400 hover:text-rose-600 bg-white hover:bg-rose-50 rounded-md border border-slate-200 hover:border-rose-300 transition-all disabled:opacity-30 disabled:cursor-not-allowed shadow-2xs"
                  title="Hapus Lowongan Ini (Delete)"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setCurrentJobId('')
                    setCurrentJobTitle('')
                    setJobTitle('')
                    setJobDescription('')
                    setJobLocation('')
                    setRequirements([])
                    setUploadedFiles([])
                    setCandidates([])
                    setCriteriaApproved(false)
                    setCurrentStep('setup')
                  }}
                  className="h-6.5 px-2 text-[11px] bg-indigo-600 hover:bg-indigo-700 text-white rounded-md font-medium transition-all flex items-center space-x-1 shadow-2xs"
                  title="Buat Lowongan Baru"
                >
                  <Plus className="w-3 h-3" />
                  <span className="hidden sm:inline font-semibold">Baru</span>
                </button>
              </div>
            </div>
          ) : (
            <p className="text-xs text-slate-500 font-medium hidden sm:inline">Platform Evaluasi & Pemeringkatan Kandidat Berpresisi Tinggi</p>
          )}
        </div>

        {/* Right Section: Global Workflow Stepper with Strict Gating */}
        <nav className="flex items-center space-x-1 bg-slate-100/90 border border-slate-200/60 p-1 rounded-xl text-xs font-medium shadow-2xs">
          <button
            onClick={() => setCurrentStep('setup')}
            className={`px-3 py-1.5 rounded-lg flex items-center space-x-1.5 transition-all cursor-pointer ${
              currentStep === 'setup' ? 'bg-white text-indigo-700 shadow-2xs font-bold' : 'text-slate-600 hover:text-slate-900 hover:bg-white/60'
            }`}
          >
            <Briefcase className="w-3.5 h-3.5" />
            <span>1. Setup Lowongan</span>
          </button>
          <button
            onClick={() => requirements.length > 0 && setCurrentStep('requirements')}
            disabled={requirements.length === 0}
            className={`px-3 py-1.5 rounded-lg flex items-center space-x-1.5 transition-all ${
              currentStep === 'requirements'
                ? 'bg-white text-indigo-700 shadow-2xs font-bold'
                : requirements.length > 0
                ? 'text-slate-600 hover:text-slate-900 hover:bg-white/60 cursor-pointer'
                : 'text-slate-400 opacity-40 cursor-not-allowed'
            }`}
            title={requirements.length === 0 ? 'Klik Ekstrak Kriteria terlebih dahulu' : '1b. Kriteria'}
          >
            <FileText className="w-3.5 h-3.5" />
            <span>1b. Kriteria{requirements.length > 0 ? ` (${requirements.length})` : ''}</span>
            {criteriaApproved && <CheckCircle2 className="w-3 h-3 text-emerald-600 ml-0.5" />}
          </button>
          <button
            onClick={() => criteriaApproved && setCurrentStep('upload')}
            disabled={!criteriaApproved}
            className={`px-3 py-1.5 rounded-lg flex items-center space-x-1.5 transition-all ${
              currentStep === 'upload'
                ? 'bg-white text-indigo-700 shadow-2xs font-bold'
                : criteriaApproved
                ? 'text-slate-600 hover:text-slate-900 hover:bg-white/60 cursor-pointer'
                : 'text-slate-400 opacity-40 cursor-not-allowed'
            }`}
            title={!criteriaApproved ? 'Kunci kriteria di step 1b terlebih dahulu' : '2. Upload CV'}
          >
            <Upload className="w-3.5 h-3.5" />
            <span>
              2. Upload CV{uploadedFiles.length > 0 ? ` (${uploadedFiles.filter((f) => f.status === 'ready').length})` : ''}
            </span>
          </button>
          <button
            onClick={() => candidates.length > 0 && setCurrentStep('leaderboard')}
            disabled={candidates.length === 0}
            className={`px-3 py-1.5 rounded-lg flex items-center space-x-1.5 transition-all ${
              currentStep === 'leaderboard'
                ? 'bg-white text-indigo-700 shadow-2xs font-bold'
                : candidates.length > 0
                ? 'text-slate-600 hover:text-slate-900 hover:bg-white/60 cursor-pointer'
                : 'text-slate-400 opacity-40 cursor-not-allowed'
            }`}
            title={candidates.length === 0 ? 'Jalankan screening terlebih dahulu' : '3. Leaderboard'}
          >
            <Trophy className={`w-3.5 h-3.5 ${candidates.length > 0 ? 'text-amber-500' : 'text-slate-400'}`} />
            <span>
              3. Leaderboard{candidates.length > 0 ? ` (${candidates.length})` : ''}
            </span>
          </button>
        </nav>
      </header>

      {/* Mandatory Objective Reminder Banner */}
      <div className="bg-amber-50 border-b border-amber-200/80 px-6 py-2 text-xs text-amber-800 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
          <span><strong>Peringatan Kebijakan:</strong> Peringkat ini adalah rekomendasi objektif berbasis bukti nyata CV. Keputusan akhir rekrutmen tetap berada di tangan manusia.</span>
        </div>
        <span className="text-amber-700/80 font-mono text-[11px]">Model: Harrier-270m (640d) • Aturan Deterministik</span>
      </div>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6">
        {/* ============================================================== */}
        {/* SCREEN 1: Setup Lowongan                                       */}
        {/* ============================================================== */}
        {currentStep === 'setup' && (
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-6 max-w-3xl mx-auto space-y-6">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Setup Lowongan Kerja</h2>
              <p className="text-sm text-slate-500">Tentukan rincian lowongan dan masukkan deskripsi pekerjaan untuk menyusun kriteria evaluasi.</p>
            </div>

            {/* Role Templates Quick Selector */}
            <div className="bg-gradient-to-r from-indigo-50/80 via-slate-50 to-indigo-50/40 border border-indigo-100/80 rounded-xl p-4 shadow-2xs">
              <div className="flex items-center justify-between mb-2.5">
                <span className="text-xs font-bold text-indigo-950 flex items-center space-x-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
                  <span>Pilih Template Role Standar Industri:</span>
                </span>
                <span className="text-[11px] text-slate-500 hidden sm:inline">1-Klik otomatis mengisi form & standar ATS</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {ROLE_TEMPLATES.map((tmpl) => (
                  <button
                    key={tmpl.id}
                    type="button"
                    onClick={() => {
                      setJobTitle(tmpl.title)
                      setJobLocation(tmpl.location)
                      setJobType(tmpl.employmentType)
                      setJobDescription(tmpl.jd_text)
                    }}
                    className="text-xs px-2.5 py-1.5 rounded-lg bg-white border border-slate-200 text-slate-700 hover:text-indigo-600 hover:border-indigo-300 hover:bg-indigo-50/60 font-semibold transition-all shadow-2xs hover:shadow-xs active:scale-98"
                  >
                    {tmpl.role}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Judul Posisi *</label>
                <input
                  type="text"
                  value={jobTitle}
                  onChange={(e) => setJobTitle(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-hidden"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Lokasi</label>
                  <input
                    type="text"
                    value={jobLocation}
                    onChange={(e) => setJobLocation(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-hidden"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Tipe Kerja</label>
                  <input
                    type="text"
                    value={jobType}
                    onChange={(e) => setJobType(e.target.value)}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-hidden"
                  />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-xs font-semibold text-slate-700">Deskripsi Lowongan (Job Description) *</label>
                  <span className="text-[11px] text-slate-500 flex items-center space-x-1">
                    <Sparkles className="w-3 h-3 text-indigo-500" />
                    <span>Kriteria otomatis diekstrak & dikompilasi dari teks ini</span>
                  </span>
                </div>
                <textarea
                  rows={9}
                  value={jobDescription}
                  onChange={(e) => setJobDescription(e.target.value)}
                  placeholder="Ketik atau tempel deskripsi lowongan kerja lengkap di sini..."
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm font-mono focus:ring-2 focus:ring-indigo-500 focus:outline-hidden leading-relaxed"
                />
                <p className="text-[11px] text-slate-400 mt-1">
                  💡 Tips: Cantumkan tanggung jawab dan kualifikasi menggunakan tanda strip (-) atau poin baris agar AI & Policy Linter dapat menyusun kriteria terstruktur dengan presisi tinggi.
                </p>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
              <span className="text-xs text-slate-400">Status Kriteria: {criteriaApproved ? 'Sudah Disetujui (v1)' : 'Draf'}</span>
              <button
                onClick={handleCompileFromJd}
                disabled={isCompiling}
                className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-sm rounded-lg shadow-xs flex items-center space-x-2 transition-colors disabled:opacity-50"
              >
                {isCompiling ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Mengekstrak Kriteria dari JD...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    <span>Ekstrak Kriteria & Lanjut</span>
                    <ChevronRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* SCREEN 1B: Tinjau & Setujui Kriteria                          */}
        {/* ============================================================== */}
        {currentStep === 'requirements' && (
          <div className="space-y-6">
            <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-lg font-bold text-slate-900 flex items-center space-x-2">
                    <span>Tinjau & Setujui Kriteria Lowongan</span>
                    <span className="text-xs bg-indigo-50 text-indigo-700 border border-indigo-200 px-2 py-0.5 rounded font-mono">
                      Versi {criteriaVersion} {criteriaApproved ? '(Terkunci)' : '(Draf)'}
                    </span>
                  </h2>
                  <p className="text-xs text-slate-500 mt-0.5">Kriteria disusun secara terstruktur dari deskripsi lowongan dan dapat disesuaikan bobotnya sebelum proses screening.</p>
                </div>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={handleCompileFromJd}
                    disabled={isCompiling}
                    className="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium text-xs rounded-lg border border-slate-200 flex items-center space-x-1.5 transition-colors disabled:opacity-50"
                  >
                    <RotateCcw className={`w-3.5 h-3.5 ${isCompiling ? 'animate-spin' : ''}`} />
                    <span>{isCompiling ? 'Mengekstrak...' : 'Kompilasi Ulang dari JD'}</span>
                  </button>
                  <button
                    onClick={handleApproveCriteria}
                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-medium text-xs rounded-lg shadow-xs flex items-center space-x-1.5 transition-colors"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Setujui Kriteria (Kunci Versi)</span>
                  </button>
                </div>
              </div>

              {/* Prohibited Alert if triggered */}
              {prohibitedFlags.length > 0 && (
                <div className="bg-rose-50 border border-rose-200 p-3 rounded-lg mb-4 text-xs text-rose-800 flex items-start space-x-2">
                  <ShieldAlert className="w-4 h-4 text-rose-600 mt-0.5 shrink-0" />
                  <div>
                    <p className="font-bold">Kriteria Diskriminatif Terlarang Terdeteksi:</p>
                    <ul className="list-disc list-inside mt-1 space-y-0.5">
                      {prohibitedFlags.map((flg, idx) => (
                        <li key={idx}>{flg}</li>
                      ))}
                    </ul>
                    <p className="mt-1 text-rose-700 font-medium">Hapus atau edit kriteria di atas untuk dapat mengaktifkan persetujuan.</p>
                  </div>
                </div>
              )}

              {/* Category Weight Summary Bar */}
              <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 mb-5 text-xs shadow-2xs">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
                  <div className="flex items-center space-x-2">
                    <span className="font-bold text-slate-800">Distribusi Bobot Kategori (Total 100%):</span>
                    {totalCategoryWeight !== 100 ? (
                      <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-rose-100 text-rose-700 border border-rose-200 animate-pulse">
                        ⚠️ Total: {totalCategoryWeight}% (Harus 100%)
                      </span>
                    ) : (
                      <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200 flex items-center space-x-1">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                        <span>Total 100% Seimbang</span>
                      </span>
                    )}
                  </div>
                  <span className="text-[11px] text-slate-500">Bobot kategori menentukan persentase porsi nilai akhir</span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="bg-white p-2.5 rounded-lg border border-slate-200 flex items-center justify-between">
                    <div>
                      <div className="text-[11px] font-semibold text-blue-700">Pengalaman</div>
                      <div className="text-[10px] text-slate-400">EXPERIENCE</div>
                    </div>
                    <div className="flex items-center space-x-1">
                      <input
                        type="number"
                        min="0"
                        max="100"
                        value={categoryWeights.EXPERIENCE ?? 40}
                        onChange={(e) => {
                          const val = Math.max(0, Math.min(100, parseInt(e.target.value) || 0))
                          setCategoryWeights({ ...categoryWeights, EXPERIENCE: val })
                          setCriteriaApproved(false)
                        }}
                        className="w-12 px-1 py-1 text-center font-mono font-bold text-slate-900 border border-slate-200 hover:border-slate-300 focus:border-indigo-500 rounded text-xs bg-slate-50 focus:bg-white focus:outline-hidden"
                      />
                      <span className="font-mono text-slate-400 text-xs">%</span>
                    </div>
                  </div>

                  <div className="bg-white p-2.5 rounded-lg border border-slate-200 flex items-center justify-between">
                    <div>
                      <div className="text-[11px] font-semibold text-indigo-700">Hard Skill</div>
                      <div className="text-[10px] text-slate-400">HARD_SKILLS</div>
                    </div>
                    <div className="flex items-center space-x-1">
                      <input
                        type="number"
                        min="0"
                        max="100"
                        value={categoryWeights.HARD_SKILLS ?? 30}
                        onChange={(e) => {
                          const val = Math.max(0, Math.min(100, parseInt(e.target.value) || 0))
                          setCategoryWeights({ ...categoryWeights, HARD_SKILLS: val })
                          setCriteriaApproved(false)
                        }}
                        className="w-12 px-1 py-1 text-center font-mono font-bold text-slate-900 border border-slate-200 hover:border-slate-300 focus:border-indigo-500 rounded text-xs bg-slate-50 focus:bg-white focus:outline-hidden"
                      />
                      <span className="font-mono text-slate-400 text-xs">%</span>
                    </div>
                  </div>

                  <div className="bg-white p-2.5 rounded-lg border border-slate-200 flex items-center justify-between">
                    <div>
                      <div className="text-[11px] font-semibold text-amber-700">Pendidikan</div>
                      <div className="text-[10px] text-slate-400">EDUCATION_CERT</div>
                    </div>
                    <div className="flex items-center space-x-1">
                      <input
                        type="number"
                        min="0"
                        max="100"
                        value={categoryWeights.EDUCATION_CERT ?? 15}
                        onChange={(e) => {
                          const val = Math.max(0, Math.min(100, parseInt(e.target.value) || 0))
                          setCategoryWeights({ ...categoryWeights, EDUCATION_CERT: val })
                          setCriteriaApproved(false)
                        }}
                        className="w-12 px-1 py-1 text-center font-mono font-bold text-slate-900 border border-slate-200 hover:border-slate-300 focus:border-indigo-500 rounded text-xs bg-slate-50 focus:bg-white focus:outline-hidden"
                      />
                      <span className="font-mono text-slate-400 text-xs">%</span>
                    </div>
                  </div>

                  <div className="bg-white p-2.5 rounded-lg border border-slate-200 flex items-center justify-between">
                    <div>
                      <div className="text-[11px] font-semibold text-purple-700">Pencapaian</div>
                      <div className="text-[10px] text-slate-400">ACHIEVEMENT</div>
                    </div>
                    <div className="flex items-center space-x-1">
                      <input
                        type="number"
                        min="0"
                        max="100"
                        value={categoryWeights.ACHIEVEMENT ?? 15}
                        onChange={(e) => {
                          const val = Math.max(0, Math.min(100, parseInt(e.target.value) || 0))
                          setCategoryWeights({ ...categoryWeights, ACHIEVEMENT: val })
                          setCriteriaApproved(false)
                        }}
                        className="w-12 px-1 py-1 text-center font-mono font-bold text-slate-900 border border-slate-200 hover:border-slate-300 focus:border-indigo-500 rounded text-xs bg-slate-50 focus:bg-white focus:outline-hidden"
                      />
                      <span className="font-mono text-slate-400 text-xs">%</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Editable Criteria Table */}
              <div className="overflow-x-auto border border-slate-200 rounded-lg shadow-2xs">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-100 text-slate-700 font-semibold uppercase tracking-wider border-b border-slate-200">
                    <tr>
                      <th className="py-2.5 px-3 w-12">ID</th>
                      <th className="py-2.5 px-3">Kriteria & Spesifikasi</th>
                      <th className="py-2.5 px-3 w-40">Kategori</th>
                      <th className="py-2.5 px-3 w-36">Tingkat</th>
                      <th className="py-2.5 px-3 w-28 text-center" title="Bobot poin relatif dalam kategorinya">Bobot Poin</th>
                      <th className="py-2.5 px-3">Kutipan Sumber di JD</th>
                      <th className="py-2.5 px-3 w-12 text-center">Aksi</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-normal bg-white">
                    {requirements.map((r, i) => (
                      <tr key={r.requirement_id || i} className="hover:bg-slate-50/80 transition-colors">
                        <td className="py-2.5 px-3 font-mono font-bold text-indigo-700">{r.requirement_id}</td>
                        <td className="py-2.5 px-3">
                          <div
                            onClick={() => handleOpenReqModal(i)}
                            className="group cursor-pointer p-1.5 -m-1 rounded-lg hover:bg-indigo-50/70 border border-transparent hover:border-indigo-200 transition-all flex items-start justify-between gap-2"
                            title="Klik untuk melihat teks kriteria lengkap & edit dalam popup"
                          >
                            <span className="font-medium text-slate-900 group-hover:text-indigo-950 line-clamp-2 leading-relaxed text-xs">
                              {r.description}
                            </span>
                            <span className="shrink-0 p-1 text-slate-400 group-hover:text-indigo-600 bg-slate-50 group-hover:bg-indigo-100/60 rounded border border-slate-200 group-hover:border-indigo-300 transition-colors shadow-2xs">
                              <Pencil className="w-3 h-3" />
                            </span>
                          </div>
                        </td>
                        <td className="py-2.5 px-3">
                          <select
                            value={
                              r.category === 'EDUCATION_CERTIFICATION'
                                ? 'EDUCATION_CERT'
                                : r.category === 'ACHIEVEMENT_LEADERSHIP'
                                ? 'ACHIEVEMENT'
                                : r.category
                            }
                            onChange={(e) => {
                              const updated = [...requirements]
                              updated[i].category = e.target.value
                              setRequirements(updated)
                              setCriteriaApproved(false)
                            }}
                            className="w-full text-[11px] font-medium rounded-md px-2 py-1 bg-slate-50 hover:bg-white border border-slate-200 hover:border-slate-300 text-slate-700 focus:outline-hidden focus:ring-1 focus:ring-indigo-500"
                          >
                            <option value="EXPERIENCE">Pengalaman</option>
                            <option value="HARD_SKILLS">Hard Skill</option>
                            <option value="EDUCATION_CERT">Pendidikan & Sertifikasi</option>
                            <option value="ACHIEVEMENT">Pencapaian & Leadership</option>
                          </select>
                        </td>
                        <td className="py-2.5 px-3">
                          <select
                            value={r.importance}
                            onChange={(e) => {
                              const updated = [...requirements]
                              updated[i].importance = e.target.value
                              setRequirements(updated)
                              setCriteriaApproved(false)
                            }}
                            className={`w-full text-[11px] font-bold rounded-md px-2 py-1 border transition-colors cursor-pointer focus:outline-hidden focus:ring-1 focus:ring-indigo-500 ${
                              r.importance === 'MUST_HAVE'
                                ? 'bg-rose-50 text-rose-700 border-rose-200 hover:bg-rose-100'
                                : r.importance === 'STRONG_PREFERENCE'
                                ? 'bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100'
                                : 'bg-slate-100 text-slate-700 border-slate-200 hover:bg-slate-200'
                            }`}
                          >
                            <option value="MUST_HAVE">🔴 Wajib</option>
                            <option value="STRONG_PREFERENCE">🟡 Diutamakan</option>
                            <option value="NICE_TO_HAVE">⚪ Nilai Tambah</option>
                          </select>
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          <div className="flex items-center justify-center space-x-1">
                            <input
                              type="number"
                              min="1"
                              max="100"
                              value={r.weight}
                              onChange={(e) => {
                                const val = parseFloat(e.target.value) || 0
                                const updated = [...requirements]
                                updated[i].weight = val
                                setRequirements(updated)
                                setCriteriaApproved(false)
                              }}
                              className="w-14 px-1 py-1 text-center font-mono font-bold text-slate-900 border border-slate-200 hover:border-slate-300 focus:border-indigo-500 rounded text-xs bg-slate-50 focus:bg-white focus:outline-hidden"
                            />
                            <span className="font-medium text-slate-500 text-[11px]">Poin</span>
                          </div>
                        </td>
                        <td className="py-2.5 px-3 text-slate-500 italic max-w-xs truncate" title={r.source_text}>
                          "{r.source_text || '-'}"
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          <button
                            onClick={() => {
                              setRequirements(requirements.filter((_, idx) => idx !== i))
                              setCriteriaApproved(false)
                            }}
                            className="text-slate-400 hover:text-rose-600 transition-colors"
                            title="Hapus Kriteria"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Add Manual Criteria Box */}
              <div className="mt-4 pt-4 border-t border-slate-100 flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5">
                <input
                  type="text"
                  placeholder="Kriteria baru (contoh: Memahami arsitektur event-driven)..."
                  value={newReqDesc}
                  onChange={(e) => setNewReqDesc(e.target.value)}
                  className="flex-1 px-3 py-2 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-indigo-500 focus:outline-hidden"
                />
                <select
                  value={newReqCategory}
                  onChange={(e) => setNewReqCategory(e.target.value)}
                  className="px-2.5 py-2 border border-slate-300 rounded-lg text-xs bg-white text-slate-700 focus:outline-hidden"
                >
                  <option value="HARD_SKILLS">Hard Skill</option>
                  <option value="EXPERIENCE">Pengalaman</option>
                  <option value="EDUCATION_CERT">Pendidikan</option>
                  <option value="ACHIEVEMENT">Pencapaian</option>
                </select>
                <select
                  value={newReqImportance}
                  onChange={(e) => setNewReqImportance(e.target.value)}
                  className="px-2.5 py-2 border border-slate-300 rounded-lg text-xs bg-white text-slate-700 focus:outline-hidden"
                >
                  <option value="MUST_HAVE">🔴 Wajib</option>
                  <option value="STRONG_PREFERENCE">🟡 Diutamakan</option>
                  <option value="NICE_TO_HAVE">⚪ Nilai Tambah</option>
                </select>
                <div className="flex items-center space-x-1 shrink-0">
                  <span className="text-[11px] text-slate-500 font-medium">Poin:</span>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={newReqWeight}
                    onChange={(e) => setNewReqWeight(parseInt(e.target.value) || 10)}
                    className="w-14 px-1.5 py-2 border border-slate-300 rounded-lg text-xs font-mono font-bold text-center bg-white focus:outline-hidden"
                  />
                  <span className="text-xs text-slate-500 font-medium">Poin</span>
                </div>
                <button
                  onClick={handleAddRequirement}
                  className="px-4 py-2 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 text-xs font-semibold rounded-lg flex items-center justify-center space-x-1.5 transition-colors shrink-0 shadow-2xs"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Tambah</span>
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between">
              <button
                onClick={() => setCurrentStep('setup')}
                className="px-4 py-2 text-slate-600 hover:text-slate-900 text-xs font-medium"
              >
                ← Kembali ke Setup
              </button>
              <button
                onClick={() => setCurrentStep('upload')}
                className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-xs rounded-lg shadow-xs flex items-center space-x-1.5 transition-colors"
              >
                <span>Lanjut ke Upload CV</span>
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* Requirement Detail & Edit Modal Popup */}
        {editingReqData && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-150">
            <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-2xl overflow-hidden flex flex-col max-h-[90vh]">
              {/* Modal Header */}
              <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50/80">
                <div className="flex items-center space-x-2.5">
                  <div className="h-8 w-8 rounded-lg bg-indigo-100 border border-indigo-200 flex items-center justify-center text-indigo-700 font-bold font-mono text-xs">
                    {editingReqData.requirement_id || 'REQ'}
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-slate-900 leading-tight">Detail & Edit Kriteria ({editingReqData.requirement_id})</h3>
                    <p className="text-[11px] text-slate-500">Lihat seluruh teks kriteria secara utuh dan sesuaikan parameter penilaian.</p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={handleCancelReqModal}
                  className="h-8 w-8 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 inline-flex items-center justify-center transition-colors cursor-pointer"
                  title="Tutup (Batal)"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Modal Body */}
              <div className="p-6 overflow-y-auto space-y-4 text-xs">
                {/* Full Description Textarea */}
                <div>
                  <label className="block text-xs font-bold text-slate-800 mb-1.5 flex items-center justify-between">
                    <span>Teks Kriteria & Spesifikasi Lengkap:</span>
                    <span className="text-[11px] font-normal text-indigo-600">Dapat diedit bebas</span>
                  </label>
                  <textarea
                    rows={4}
                    value={editingReqData.description}
                    onChange={(e) => setEditingReqData({ ...editingReqData, description: e.target.value })}
                    className="w-full p-3 text-xs leading-relaxed text-slate-900 bg-white border border-slate-300 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 focus:outline-hidden transition-all shadow-2xs resize-y"
                    placeholder="Ketik deskripsi lengkap kriteria..."
                  />
                </div>

                {/* Grid 2 Columns: Category & Importance */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Kategori Penilaian:
                    </label>
                    <select
                      value={
                        editingReqData.category === 'EDUCATION_CERTIFICATION'
                          ? 'EDUCATION_CERT'
                          : editingReqData.category === 'ACHIEVEMENT_LEADERSHIP'
                          ? 'ACHIEVEMENT'
                          : editingReqData.category
                      }
                      onChange={(e) => setEditingReqData({ ...editingReqData, category: e.target.value })}
                      className="w-full text-xs font-medium rounded-lg px-3 py-2 bg-slate-50 border border-slate-300 text-slate-800 focus:bg-white focus:ring-2 focus:ring-indigo-500 focus:outline-hidden transition-colors cursor-pointer"
                    >
                      <option value="EXPERIENCE">Pengalaman Kerja (EXPERIENCE)</option>
                      <option value="HARD_SKILLS">Hard Skill & Teknologi (HARD_SKILLS)</option>
                      <option value="EDUCATION_CERT">Pendidikan & Sertifikasi (EDUCATION_CERT)</option>
                      <option value="ACHIEVEMENT">Pencapaian & Kepemimpinan (ACHIEVEMENT)</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Tingkat Kepentingan:
                    </label>
                    <select
                      value={editingReqData.importance}
                      onChange={(e) => setEditingReqData({ ...editingReqData, importance: e.target.value })}
                      className={`w-full text-xs font-bold rounded-lg px-3 py-2 border transition-colors cursor-pointer focus:outline-hidden focus:ring-2 focus:ring-indigo-500 ${
                        editingReqData.importance === 'MUST_HAVE'
                          ? 'bg-rose-50 text-rose-800 border-rose-300'
                          : editingReqData.importance === 'STRONG_PREFERENCE'
                          ? 'bg-amber-50 text-amber-800 border-amber-300'
                          : 'bg-slate-100 text-slate-800 border-slate-300'
                      }`}
                    >
                      <option value="MUST_HAVE">🔴 Wajib (MUST_HAVE)</option>
                      <option value="STRONG_PREFERENCE">🟡 Diutamakan (STRONG_PREFERENCE)</option>
                      <option value="NICE_TO_HAVE">⚪ Nilai Tambah (NICE_TO_HAVE)</option>
                    </select>
                  </div>
                </div>

                {/* Grid 2 Columns: Weight & Concepts */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Bobot Kriteria (Poin Relatif):
                    </label>
                    <div className="flex items-center space-x-2">
                      <input
                        type="number"
                        min="1"
                        max="100"
                        value={editingReqData.weight}
                        onChange={(e) => setEditingReqData({ ...editingReqData, weight: parseFloat(e.target.value) || 0 })}
                        className="w-24 px-3 py-2 font-mono font-bold text-slate-900 border border-slate-300 rounded-lg text-xs bg-slate-50 focus:bg-white focus:ring-2 focus:ring-indigo-500 focus:outline-hidden"
                      />
                      <span className="font-mono text-slate-500 text-xs font-semibold">Poin</span>
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Tag Konsep Ontologi:
                    </label>
                    <div className="flex flex-wrap gap-1.5 min-h-[36px] items-center p-2 bg-slate-50 border border-slate-200 rounded-lg">
                      {editingReqData.concepts && editingReqData.concepts.length > 0 ? (
                        editingReqData.concepts.map((c, cIdx) => (
                          <span key={cIdx} className="px-2 py-0.5 bg-indigo-50 text-indigo-700 border border-indigo-200/80 rounded-md font-mono text-[10px]">
                            {c}
                          </span>
                        ))
                      ) : (
                        <span className="text-slate-400 italic text-[11px]">Tidak ada konsep terpetakan</span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Source Text from Job Description */}
                {editingReqData.source_text && (
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">
                      Kutipan Asli dari Deskripsi Lowongan (Source Quote):
                    </label>
                    <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-slate-700 italic leading-relaxed text-xs">
                      "{editingReqData.source_text}"
                    </div>
                  </div>
                )}
              </div>

              {/* Modal Footer Actions */}
              <div className="px-6 py-3.5 bg-slate-50 border-t border-slate-200 flex items-center justify-between">
                <span className="text-[11px] text-slate-500 hidden sm:inline">
                  Perubahan akan memperbarui draf kriteria.
                </span>
                <div className="flex items-center space-x-2 ml-auto">
                  <button
                    type="button"
                    onClick={handleCancelReqModal}
                    className="px-4 py-2 text-xs font-semibold text-slate-700 hover:text-slate-900 bg-white hover:bg-slate-100 border border-slate-300 rounded-lg transition-colors cursor-pointer shadow-2xs"
                  >
                    Batal
                  </button>
                  <button
                    type="button"
                    onClick={handleSaveReqModal}
                    className="px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg transition-colors flex items-center space-x-1.5 cursor-pointer shadow-xs"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Simpan Perubahan</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* SCREEN 2: Upload CV Dropzone                                   */}
        {/* ============================================================== */}
        {currentStep === 'upload' && (
          <div className="space-y-6 max-w-4xl mx-auto">
            <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-lg font-bold text-slate-900">Upload CV Pelamar</h2>
                  <p className="text-xs text-slate-500">Mendukung format PDF, DOCX, scan gambar, dan arsip ZIP berukuran hingga 10 MB per berkas.</p>
                </div>
                <div className="flex items-center space-x-2">
                  <button
                    type="button"
                    onClick={handleManualRefresh}
                    disabled={isRefreshing}
                    className="text-xs text-slate-700 hover:text-indigo-700 bg-white hover:bg-slate-50 border border-slate-200 px-2.5 py-1 rounded-md font-medium transition-colors flex items-center space-x-1.5 shadow-2xs disabled:opacity-50"
                    title="Segarkan status berkas CV dari server"
                  >
                    <RotateCcw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-indigo-600' : 'text-slate-500'}`} />
                    <span>Perbarui Status</span>
                  </button>
                  {uploadedFiles.length > 0 && (
                    <button
                      onClick={handleClearUploadedCvs}
                      className="text-xs text-rose-600 hover:text-rose-800 bg-rose-50 border border-rose-200 px-2.5 py-1 rounded-md font-medium transition-colors flex items-center space-x-1"
                      title="Hapus semua berkas CV yang telah diunggah untuk lowongan ini"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      <span>Kosongkan Berkas</span>
                    </button>
                  )}
                  <button
                    onClick={handleLoadSampleCvs}
                    className="text-xs text-indigo-600 hover:text-indigo-800 bg-indigo-50 border border-indigo-200 px-2.5 py-1 rounded-md font-medium transition-colors"
                  >
                    🧪 Muat 15 Sampel Golden Dataset
                  </button>
                  <span className="text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-1 rounded-md">
                    {uploadedFiles.filter((f) => f.status === 'ready').length} CV Siap Dinilai
                  </span>
                  {uploadedFiles.some((f) => f.status === 'duplicate') && (
                    <span className="text-xs font-medium text-slate-600 bg-slate-100 border border-slate-200 px-2.5 py-1 rounded-md">
                      {uploadedFiles.filter((f) => f.status === 'duplicate').length} Duplikat Diabaikan
                    </span>
                  )}
                </div>
              </div>

              {/* Drag and Drop Zone */}
              <input
                type="file"
                ref={fileInputRef}
                multiple
                accept=".pdf,.docx,.doc,.zip,.jpg,.jpeg,.png"
                onChange={handleFileInputChange}
                className="hidden"
              />
              <div
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => {
                  e.preventDefault()
                  setIsDragging(true)
                }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleFileDrop}
                className={`border-2 border-dashed rounded-xl p-8 text-center transition-all cursor-pointer ${
                  isDragging
                    ? 'border-indigo-600 bg-indigo-100/60 scale-[1.01]'
                    : 'border-indigo-200 bg-indigo-50/30 hover:bg-indigo-50/60'
                }`}
              >
                <Upload
                  className={`w-10 h-10 text-indigo-500 mx-auto mb-2 ${
                    isUploading ? 'animate-bounce text-indigo-600' : ''
                  }`}
                />
                <h3 className="text-sm font-bold text-slate-800">
                  {isUploading
                    ? uploadStatusMsg || 'Sedang memproses upload berkas...'
                    : 'Tarik berkas CV ke sini atau klik untuk memilih'}
                </h3>
                <p className="text-xs text-slate-500 mt-1">PDF, DOCX, DOC, JPG, PNG, atau ZIP (Maksimal 10 MB per file)</p>
                <div className="mt-4 flex items-center justify-center space-x-2">
                  <span className="text-[11px] bg-white border border-slate-200 px-2.5 py-1 rounded text-slate-600 shadow-2xs font-mono">
                    {uploadedFiles.length > 0
                      ? `${uploadedFiles.length} Berkas CV Terdeteksi`
                      : 'Pilih satu atau banyak berkas CV'}
                  </span>
                </div>
              </div>

              {/* Progress Summary */}
              <div className="mt-6">
                <div className="flex items-center justify-between text-xs mb-1.5 font-medium">
                  <span className="text-slate-700">
                    Kemajuan Ingestion & Sanitizer: {uploadedFiles.filter((f) => f.status !== 'processing').length}/
                    {uploadedFiles.length} CV Berhasil Diproses
                  </span>
                  <span className="text-emerald-700 font-bold">
                    {uploadedFiles.length > 0
                      ? `${Math.round(
                          (uploadedFiles.filter((f) => f.status !== 'processing').length / uploadedFiles.length) * 100
                        )}% Siap`
                      : 'Menunggu Berkas'}
                  </span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-emerald-500 h-2 rounded-full transition-all duration-300"
                    style={{
                      width: `${
                        uploadedFiles.length > 0
                          ? Math.round(
                              (uploadedFiles.filter((f) => f.status !== 'processing').length / uploadedFiles.length) * 100
                            )
                          : 0
                      }%`,
                    }}
                  ></div>
                </div>
              </div>

              {/* Files Table List */}
              <div className="mt-6 border border-slate-200 rounded-lg overflow-hidden">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-100 text-slate-700 font-semibold uppercase tracking-wider border-b border-slate-200">
                    <tr>
                      <th className="py-2.5 px-3">Nama Berkas</th>
                      <th className="py-2.5 px-3 w-24">Ukuran</th>
                      <th className="py-2.5 px-3 w-36">Status</th>
                      <th className="py-2.5 px-3 max-w-xs">Catatan / Alasan Pemeriksaan</th>
                      <th className="py-2.5 px-3 w-24 text-center">Aksi</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {uploadedFiles.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="py-8 text-center text-slate-400">
                          <FileText className="w-8 h-8 mx-auto mb-1 text-slate-300" />
                          <p className="font-medium text-slate-600">Belum ada berkas CV yang diunggah.</p>
                          <p className="text-[11px] text-slate-400 mt-0.5">
                            Tarik dan letakkan berkas PDF/DOCX di atas atau klik untuk memilih file.
                          </p>
                        </td>
                      </tr>
                    ) : (
                      uploadedFiles.map((file, idx) => (
                        <tr key={idx} className="hover:bg-slate-50 transition-colors">
                          <td className="py-2 px-3 font-medium text-slate-900 flex items-center space-x-2">
                            {file.status === 'processing' ? (
                              <Loader2 className="w-3.5 h-3.5 text-indigo-600 animate-spin shrink-0" />
                            ) : (
                              <FileCheck className="w-3.5 h-3.5 text-indigo-600 shrink-0" />
                            )}
                            <span className="truncate max-w-[200px]" title={file.name}>{file.name}</span>
                          </td>
                          <td className="py-2 px-3 text-slate-500 font-mono text-[11px]">{file.size}</td>
                          <td className="py-2 px-3">
                            <span
                              className={`px-2 py-0.5 rounded text-[11px] font-bold inline-flex items-center space-x-1 ${
                                file.status === 'ready'
                                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                  : file.status === 'processing'
                                  ? 'bg-blue-50 text-blue-700 border border-blue-200 animate-pulse'
                                  : file.status === 'review'
                                  ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                  : file.status === 'duplicate'
                                  ? 'bg-slate-100 text-slate-600 border border-slate-200'
                                  : 'bg-rose-50 text-rose-700 border border-rose-200'
                              }`}
                            >
                              <span>
                                {file.status === 'ready'
                                  ? 'Siap'
                                  : file.status === 'processing'
                                  ? 'Diproses...'
                                  : file.status === 'review'
                                  ? 'Perlu Cek Manual'
                                  : file.status === 'duplicate'
                                  ? 'Duplikat'
                                  : 'Tidak Memenuhi Syarat'}
                              </span>
                            </span>
                          </td>
                          <td className="py-2 px-3 text-slate-500 text-[11px] italic max-w-xs truncate" title={file.reason}>
                            {file.reason || 'Ekstraksi identitas & keahlian terverifikasi'}
                          </td>
                          <td className="py-2 px-3 text-center">
                            <div className="flex items-center justify-center space-x-1.5">
                              {file.id && (
                                <>
                                  <button
                                    type="button"
                                    onClick={() => handleRetrySingleCv(file.id)}
                                    className="p-1.5 text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 border border-slate-200 rounded transition-colors"
                                    title="Coba proses ulang berkas ini"
                                  >
                                    <RotateCcw className="w-3.5 h-3.5" />
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => handleDeleteSingleCv(file.id, file.name)}
                                    className="p-1.5 text-slate-500 hover:text-rose-600 hover:bg-rose-50 border border-slate-200 rounded transition-colors"
                                    title="Hapus berkas ini dari perankingan"
                                  >
                                    <Trash2 className="w-3.5 h-3.5" />
                                  </button>
                                </>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="flex items-center justify-between">
              <button
                onClick={() => setCurrentStep('requirements')}
                className="px-4 py-2 text-slate-600 hover:text-slate-900 text-xs font-medium"
              >
                ← Kembali ke Kriteria
              </button>
              <button
                onClick={handleStartScreening}
                disabled={isScreening}
                className="px-6 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs rounded-lg shadow-xs flex items-center space-x-2 transition-colors disabled:opacity-50"
              >
                {isScreening ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Menjalankan Evaluasi & Scoring...</span>
                  </>
                ) : (
                  <>
                    <Trophy className="w-4 h-4" />
                    <span>Mulai Screening & Buka Leaderboard</span>
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* ============================================================== */}
        {/* SCREEN 3: Leaderboard (Hasil Ranking & Scoring)                */}
        {/* ============================================================== */}
        {currentStep === 'leaderboard' && (
          <div className="space-y-4">
            {/* Header Leaderboard */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-5 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <div>
                <div className="flex items-center space-x-2">
                  <h2 className="text-xl font-bold text-slate-900">{jobTitle}</h2>
                  <span className="text-xs bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded font-medium">
                    Run Selesai (Versi {criteriaVersion})
                  </span>
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  Tanggal Evaluasi: <strong>9 Okt 2026</strong> • Total Kandidat Dinilai: <strong>{candidates.length}</strong>
                </p>
              </div>

              <div className="flex items-center space-x-2.5">
                {selectedForCompare.length >= 2 && (
                  <button
                    onClick={() => setIsCompareOpen(true)}
                    className="px-3.5 py-2 bg-indigo-50 border border-indigo-200 hover:bg-indigo-100 text-indigo-700 rounded-lg text-xs font-bold flex items-center space-x-1.5 transition-colors"
                  >
                    <GitCompare className="w-3.5 h-3.5" />
                    <span>Bandingkan ({selectedForCompare.length})</span>
                  </button>
                )}
                <button
                  onClick={() => setIsExportOpen(true)}
                  className="px-3.5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-colors"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Export Laporan</span>
                </button>
                <button
                  onClick={() => alert('Screening ulang dieksekusi secara deterministik dengan model Harrier-270m.')}
                  className="px-3.5 py-2 bg-white hover:bg-slate-50 text-slate-600 border border-slate-300 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-colors"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Jalankan Ulang</span>
                </button>
              </div>
            </div>

            {/* Filter Tabs & Search Bar */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 bg-white p-3 rounded-xl border border-slate-200">
              {/* Band Tabs */}
              <div className="flex items-center space-x-1 text-xs">
                <button
                  onClick={() => setActiveBand('ALL')}
                  className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
                    activeBand === 'ALL' ? 'bg-indigo-600 text-white font-bold' : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  Semua ({candidates.length})
                </button>
                <button
                  onClick={() => setActiveBand('A')}
                  className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
                    activeBand === 'A' ? 'bg-emerald-600 text-white font-bold' : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  Semua Wajib Terbukti (A) ({candidates.filter((c) => c.band === 'A').length})
                </button>
                <button
                  onClick={() => setActiveBand('B')}
                  className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
                    activeBand === 'B' ? 'bg-amber-600 text-white font-bold' : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  1 Wajib Belum Terbukti (B) ({candidates.filter((c) => c.band === 'B').length})
                </button>
                <button
                  onClick={() => setActiveBand('C')}
                  className={`px-3 py-1.5 rounded-lg font-medium transition-colors ${
                    activeBand === 'C' ? 'bg-slate-700 text-white font-bold' : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  Prioritas Rendah (C) ({candidates.filter((c) => c.band === 'C').length})
                </button>
              </div>

              {/* Search box */}
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
                <input
                  type="text"
                  placeholder="Cari kandidat / berkas..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8 pr-3 py-1.5 border border-slate-300 rounded-lg text-xs w-56 focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </div>

            {/* Candidates Table */}
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-100 text-slate-700 font-semibold uppercase tracking-wider border-b border-slate-200">
                  <tr>
                    <th className="py-3 px-3 w-10 text-center">☐</th>
                    <th className="py-3 px-2 w-12 text-center">#</th>
                    <th className="py-3 px-3">Kandidat</th>
                    <th className="py-3 px-3 w-28 text-center">Skor Akhir</th>
                    <th className="py-3 px-3 w-32">Kriteria Wajib</th>
                    <th className="py-3 px-3 w-36">Rincian Kategori</th>
                    <th className="py-3 px-3 w-36">Rekomendasi</th>
                    <th className="py-3 px-3 w-28">Keputusan</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredCandidates.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="py-12 text-center text-slate-400">
                        <Trophy className="w-8 h-8 mx-auto mb-2 text-slate-300" />
                        <p className="font-medium text-slate-600">Belum ada hasil screening kandidat.</p>
                        <p className="text-[11px] text-slate-400 mt-1">
                          Unggah berkas CV di menu Upload CV, lalu klik &quot;Mulai Screening&quot; untuk menjalankan evaluasi objektif.
                        </p>
                      </td>
                    </tr>
                  ) : (
                    filteredCandidates.map((cand) => (
                    <tr
                      key={cand.cv_id}
                      onClick={() => handleSelectCandidate(cand)}
                      className="hover:bg-indigo-50/40 cursor-pointer transition-colors"
                    >
                      <td
                        className="py-3 px-3 text-center"
                        onClick={(e) => {
                          e.stopPropagation()
                          if (selectedForCompare.includes(cand.cv_id)) {
                            setSelectedForCompare(selectedForCompare.filter((id) => id !== cand.cv_id))
                          } else {
                            if (selectedForCompare.length < 4) {
                              setSelectedForCompare([...selectedForCompare, cand.cv_id])
                            } else {
                              alert('Maksimal membandingkan 4 kandidat sekaligus.')
                            }
                          }
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={selectedForCompare.includes(cand.cv_id)}
                          onChange={() => {}}
                          className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                        />
                      </td>
                      <td className="py-3 px-2 text-center font-bold font-mono text-slate-500">
                        {cand.rank}
                      </td>
                      <td className="py-3 px-3">
                        <div className="flex items-center space-x-2">
                          <span className="font-bold text-slate-900">
                            {blindMode && !cand.revealed ? cand.blind_id : cand.real_name}
                          </span>
                          {cand.flags.includes('PROMPT_INJECTION') && (
                            <span className="bg-rose-100 text-rose-700 text-[10px] px-1.5 py-0.5 rounded font-bold" title="Upaya prompt injection dinetralkan">
                              INJECTION DINUTRALKAN
                            </span>
                          )}
                        </div>
                        <span className="text-[11px] text-slate-400 font-mono block">{cand.file_name}</span>
                      </td>
                      <td className="py-3 px-3 text-center">
                        <span
                          className={`inline-block px-2.5 py-1 rounded-md font-bold font-mono text-sm ${
                            cand.final_score >= 75
                              ? 'bg-emerald-100 text-emerald-800'
                              : cand.final_score >= 50
                              ? 'bg-amber-100 text-amber-800'
                              : 'bg-rose-100 text-rose-800'
                          }`}
                        >
                          {cand.final_score.toFixed(1)}
                        </span>
                        <span className="text-[10px] text-slate-400 block mt-0.5">Band {cand.band}</span>
                      </td>
                      <td className="py-3 px-3">
                        <div className="flex items-center space-x-1">
                          {['R1', 'R2', 'R3'].map((rKey) => {
                            const st = cand.requirement_states[rKey]
                            return (
                              <div
                                key={rKey}
                                className={`w-2.5 h-2.5 rounded-full ${
                                  st === 'STRONG' ? 'bg-emerald-500' : st === 'PARTIAL' ? 'bg-amber-400' : 'bg-slate-300'
                                }`}
                                title={`${rKey}: ${st || 'Belum terbukti'}`}
                              />
                            )
                          })}
                          <span className="text-[11px] text-slate-500 ml-1.5">
                            {Object.entries(cand.requirement_states).filter(([k, v]) => ['R1', 'R2', 'R3'].includes(k) && v === 'STRONG').length}/3 Wajib
                          </span>
                        </div>
                      </td>
                      <td className="py-3 px-3">
                        <div className="space-y-1">
                          <div className="w-full bg-slate-100 h-1.5 rounded-full overflow-hidden flex">
                            <div className="bg-blue-500 h-full" style={{ width: `${cand.category_breakdown.EXPERIENCE || 0}%` }} />
                            <div className="bg-indigo-500 h-full" style={{ width: `${cand.category_breakdown.HARD_SKILLS || 0}%` }} />
                            <div className="bg-amber-500 h-full" style={{ width: `${cand.category_breakdown.EDUCATION_CERTIFICATION || 0}%` }} />
                          </div>
                          <span className="text-[10px] text-slate-400 font-mono block">
                            {cand.metrics.backend_months ? `${cand.metrics.backend_months} bln relevan` : '-'}
                          </span>
                        </div>
                      </td>
                      <td className="py-3 px-3">
                        <div className="flex flex-col gap-1 items-start">
                          <span
                            className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                              cand.recommendation === 'SHORTLIST'
                                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                : cand.recommendation === 'REVIEW'
                                ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                : cand.recommendation === 'REJECTED_NOT_A_CV' || cand.flags?.includes('NOT_A_CV')
                                ? 'bg-rose-50 text-rose-700 border border-rose-300'
                                : cand.recommendation === 'MANUAL_CHECK'
                                ? 'bg-purple-50 text-purple-700 border border-purple-200'
                                : 'bg-slate-100 text-slate-600'
                            }`}
                            title={cand.document_reasons?.join(', ')}
                          >
                            {cand.recommendation === 'SHORTLIST'
                              ? 'Disarankan Shortlist'
                              : cand.recommendation === 'REVIEW'
                              ? 'Perlu Ditinjau'
                              : cand.recommendation === 'REJECTED_NOT_A_CV' || cand.flags?.includes('NOT_A_CV')
                              ? '⛔ Bukan CV (Ditolak)'
                              : cand.recommendation === 'MANUAL_CHECK'
                              ? 'Perlu Cek Manual'
                              : 'Prioritas Rendah'}
                          </span>
                          {cand.eligibility_status === 'NOT_ELIGIBLE' && (
                            <span
                              className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-50 text-amber-800 border border-amber-200"
                              title={cand.eligibility_reasons?.join(', ') || 'Di luar kriteria administratif'}
                            >
                              ⚠️ Di luar kriteria administratif
                            </span>
                          )}
                          {cand.eligibility_status === 'UNKNOWN' && (
                            <span
                              className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-600 border border-slate-200"
                              title="Data administratif tidak tersedia di CV"
                            >
                              ℹ️ Data administratif tidak tersedia
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-3" onClick={(e) => e.stopPropagation()}>
                        <select
                          value={cand.decision || 'NONE'}
                          onChange={(e) => handleDecision(cand.cv_id, e.target.value as any)}
                          className="bg-slate-50 border border-slate-200 rounded px-2 py-1 text-xs font-medium text-slate-700 focus:outline-hidden"
                        >
                          <option value="NONE">- Belum Diputuskan -</option>
                          <option value="SHORTLIST">Shortlist</option>
                          <option value="HOLD">Tahan</option>
                          <option value="TIDAK_LANJUT">Tidak Lanjut</option>
                        </select>
                      </td>
                    </tr>
                  ))
                )}
                </tbody>
              </table>
            </div>

            {/* Box: Berkas Bermasalah / Dikecualikan dari Penilaian */}
            {uploadedFiles.some((f) => f.status === 'review' || f.status === 'unqualified' || f.status === 'duplicate') && (
              <div className="bg-amber-50/70 border border-amber-200 rounded-xl p-5 shadow-2xs space-y-3 mt-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2.5">
                    <span className="p-1.5 bg-amber-100 text-amber-800 rounded-lg">
                      <AlertTriangle className="w-4 h-4" />
                    </span>
                    <div>
                      <h4 className="text-xs font-bold text-amber-950">
                        Berkas Dikecualikan dari Penilaian Otomatis (
                        {uploadedFiles.filter((f) => f.status === 'review' || f.status === 'unqualified' || f.status === 'duplicate').length} Berkas)
                      </h4>
                      <p className="text-[11px] text-amber-800">
                        Berkas di bawah ini tidak masuk ke dalam Leaderboard karena terdeteksi format scan gambar, OCR rusak/noise, duplikat, atau butuh pemeriksaan manual.
                      </p>
                    </div>
                  </div>
                </div>

                <div className="bg-white border border-amber-200/80 rounded-lg overflow-hidden">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-amber-50 text-amber-900 font-semibold uppercase tracking-wider border-b border-amber-200/80">
                      <tr>
                        <th className="py-2.5 px-3">Nama Berkas</th>
                        <th className="py-2.5 px-3 w-36">Status</th>
                        <th className="py-2.5 px-3">Alasan / Catatan Kendala</th>
                        <th className="py-2.5 px-3 w-32 text-center">Aksi</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-amber-100">
                      {uploadedFiles
                        .filter((f) => f.status === 'review' || f.status === 'unqualified' || f.status === 'duplicate')
                        .map((f, i) => (
                          <tr key={f.id || i} className="hover:bg-amber-50/40">
                            <td className="py-2.5 px-3 font-medium text-slate-900">
                              <span className="truncate max-w-sm block" title={f.name}>{f.name}</span>
                            </td>
                            <td className="py-2.5 px-3">
                              <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                f.status === 'review'
                                  ? 'bg-amber-100 text-amber-800 border border-amber-300'
                                  : f.status === 'duplicate'
                                  ? 'bg-slate-100 text-slate-700 border border-slate-300'
                                  : 'bg-rose-100 text-rose-800 border border-rose-300'
                              }`}>
                                {f.status === 'review' ? '⚠️ Perlu Cek Manual' : f.status === 'duplicate' ? 'Duplikat' : '⛔ Dikecualikan'}
                              </span>
                            </td>
                            <td className="py-2.5 px-3 text-slate-600 text-[11px] italic">
                              {f.reason || 'Kualitas teks rendah atau scan dokumen tidak terstruktur'}
                            </td>
                            <td className="py-2.5 px-3 text-center">
                              <div className="flex items-center justify-center space-x-1.5">
                                {f.id && (
                                  <>
                                    <button
                                      type="button"
                                      onClick={() => handleRetrySingleCv(f.id)}
                                      className="px-2 py-1 bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 text-[11px] font-medium rounded shadow-2xs flex items-center space-x-1"
                                      title="Coba proses ulang dokumen ini"
                                    >
                                      <RotateCcw className="w-3 h-3 text-indigo-600" />
                                      <span>Ulang</span>
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => handleDeleteSingleCv(f.id, f.name)}
                                      className="px-2 py-1 bg-rose-50 hover:bg-rose-100 border border-rose-200 text-rose-700 text-[11px] font-medium rounded shadow-2xs flex items-center space-x-1"
                                      title="Hapus berkas ini dari lowongan"
                                    >
                                      <Trash2 className="w-3 h-3 text-rose-600" />
                                      <span>Hapus</span>
                                    </button>
                                  </>
                                )}
                              </div>
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </main>

      {/* ============================================================== */}
      {/* SCREEN 4: Candidate Detail Drawer (55% width)                  */}
      {/* ============================================================== */}
      {selectedCandidate && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-slate-900/40 backdrop-blur-2xs flex justify-end">
          <div className="w-full max-w-3xl bg-white h-full shadow-2xl flex flex-col transform transition-transform duration-200 ease-in-out border-l border-slate-200">
            {/* Drawer Header */}
            <div className="p-5 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div className="flex items-center space-x-3">
                <div
                  className={`w-12 h-12 rounded-xl flex items-center justify-center font-bold text-lg font-mono ${
                    selectedCandidate.final_score >= 75
                      ? 'bg-emerald-600 text-white'
                      : selectedCandidate.final_score >= 50
                      ? 'bg-amber-500 text-white'
                      : 'bg-slate-600 text-white'
                  }`}
                >
                  {selectedCandidate.final_score.toFixed(0)}
                </div>
                <div>
                  <div className="flex items-center space-x-2">
                    <h3 className="text-base font-bold text-slate-900">
                      {blindMode && !selectedCandidate.revealed ? selectedCandidate.blind_id : selectedCandidate.real_name}
                    </h3>
                    {blindMode && !selectedCandidate.revealed && (
                      <button
                        onClick={() => handleRevealCandidate(selectedCandidate.cv_id)}
                        className="text-[11px] text-indigo-600 hover:text-indigo-800 font-semibold underline flex items-center space-x-1"
                      >
                        <Eye className="w-3 h-3" />
                        <span>Buka Identitas</span>
                      </button>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 font-mono">{selectedCandidate.file_name} • Peringkat #{selectedCandidate.rank}</p>
                </div>
              </div>

              <button
                onClick={() => setSelectedCandidate(null)}
                className="text-slate-400 hover:text-slate-600 text-lg font-bold p-1 rounded-md"
              >
                ✕
              </button>
            </div>

            {/* Drawer Tab Navigation */}
            <div className="flex border-b border-slate-200 px-5 text-xs font-semibold bg-white">
              <button
                onClick={() => setActiveDrawerTab('ringkasan')}
                className={`py-3 px-3 border-b-2 transition-colors ${
                  activeDrawerTab === 'ringkasan' ? 'border-indigo-600 text-indigo-600 font-bold' : 'border-transparent text-slate-500 hover:text-slate-700'
                }`}
              >
                1. Ringkasan Evaluasi
              </button>
              <button
                onClick={() => setActiveDrawerTab('jejak')}
                className={`py-3 px-3 border-b-2 transition-colors ${
                  activeDrawerTab === 'jejak' ? 'border-indigo-600 text-indigo-600 font-bold' : 'border-transparent text-slate-500 hover:text-slate-700'
                }`}
              >
                2. Asal-usul Skor
              </button>
              <button
                onClick={() => setActiveDrawerTab('kartu_skor')}
                className={`py-3 px-3 border-b-2 transition-colors ${
                  activeDrawerTab === 'kartu_skor' ? 'border-indigo-600 text-indigo-600 font-bold' : 'border-transparent text-slate-500 hover:text-slate-700'
                }`}
              >
                3. Kartu Kriteria
              </button>
              <button
                onClick={() => setActiveDrawerTab('cv_asli')}
                className={`py-3 px-3 border-b-2 transition-colors ${
                  activeDrawerTab === 'cv_asli' ? 'border-indigo-600 text-indigo-600 font-bold' : 'border-transparent text-slate-500 hover:text-slate-700'
                }`}
              >
                4. Berkas CV & Kutipan
              </button>
              <button
                onClick={() => setActiveDrawerTab('riwayat')}
                className={`py-3 px-3 border-b-2 transition-colors ${
                  activeDrawerTab === 'riwayat' ? 'border-indigo-600 text-indigo-600 font-bold' : 'border-transparent text-slate-500 hover:text-slate-700'
                }`}
              >
                5. Riwayat & Keputusan
              </button>
            </div>

            {/* Drawer Body */}
            <div className="flex-1 overflow-y-auto p-5 space-y-6">
              {/* Tab 1: Ringkasan Evaluasi */}
              {activeDrawerTab === 'ringkasan' && (
                <div className="space-y-5 text-xs">
                  {/* Kelebihan Terbukti */}
                  <div className="bg-emerald-50/60 border border-emerald-200 p-4 rounded-xl">
                    <h4 className="font-bold text-emerald-900 mb-2 flex items-center space-x-1.5 text-sm">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                      <span>Kelebihan Terbukti di CV</span>
                    </h4>
                    <div className="space-y-2">
                      {selectedCandidate.explanation.strengths.map((s, idx) => (
                        <div key={idx} className="bg-white p-2.5 rounded-lg border border-emerald-100 shadow-2xs">
                          <p className="font-semibold text-slate-800">{s.description}</p>
                          <p className="text-slate-500 italic mt-0.5 text-[11px]">"{s.quote}"</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Belum Terbukti */}
                  <div className="bg-amber-50/60 border border-amber-200 p-4 rounded-xl">
                    <h4 className="font-bold text-amber-900 mb-2 flex items-center space-x-1.5 text-sm">
                      <AlertTriangle className="w-4 h-4 text-amber-600" />
                      <span>Belum Terbukti di CV</span>
                    </h4>
                    <div className="space-y-2">
                      {selectedCandidate.explanation.unproven.map((u, idx) => (
                        <div key={idx} className="bg-white p-2.5 rounded-lg border border-amber-100 shadow-2xs">
                          <p className="font-semibold text-slate-800">{u.description}</p>
                          <p className="text-amber-700 text-[11px] mt-0.5">{u.note}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Saran Pertanyaan Wawancara */}
                  <div className="bg-slate-50 border border-slate-200 p-4 rounded-xl">
                    <h4 className="font-bold text-slate-900 mb-2 text-sm">Saran Pertanyaan Wawancara Mendalam</h4>
                    <div className="space-y-2">
                      {selectedCandidate.explanation.interview_questions.map((q, idx) => (
                        <div key={idx} className="bg-white p-2.5 rounded-lg border border-slate-200 shadow-2xs">
                          <span className="font-mono text-indigo-700 font-bold block mb-0.5 text-[10px] uppercase">{q.focus}</span>
                          <p className="text-slate-800 font-medium">"{q.question}"</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Tab 2: Asal-usul Skor (score trace: score -> criterion -> facet -> CV sentence) */}
              {activeDrawerTab === 'jejak' && (
                <ScoreTracePanel
                  trace={selectedCandidate.score_trace}
                  onShowInCv={(atomKey) => {
                    setSelectedQuoteToHighlight(null)
                    setSelectedAtomKey(atomKey)
                    setActiveDrawerTab('cv_asli')
                  }}
                />
              )}

              {/* Tab 3: Kartu Skor Kriteria */}
              {activeDrawerTab === 'kartu_skor' && (
                <div className="space-y-3">
                  {requirements.map((r) => {
                    const st = selectedCandidate.requirement_states[r.requirement_id] || 'NOT_DEMONSTRATED'
                    const evList = selectedCandidate.evidence[r.requirement_id] || []
                    return (
                      <div key={r.requirement_id} className="border border-slate-200 rounded-lg p-3 bg-white">
                        <div className="flex items-center justify-between mb-1.5">
                          <div className="flex items-center space-x-2">
                            <span className="font-mono font-bold text-indigo-700 text-xs">{r.requirement_id}</span>
                            <span className="font-medium text-slate-900 text-xs">{r.description}</span>
                          </div>
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              st === 'STRONG'
                                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                : st === 'PARTIAL'
                                ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                : 'bg-slate-100 text-slate-500'
                            }`}
                          >
                            {st === 'STRONG' ? 'Terbukti' : st === 'PARTIAL' ? 'Sebagian Terpenuhi' : 'Tidak Tercantum di CV'}
                          </span>
                        </div>
                        {evList.length > 0 ? (
                          <div className="mt-2 bg-slate-50 p-2 rounded border border-slate-100 text-[11px]">
                            <p className="text-slate-600 italic">"{evList[0].quote}"</p>
                            <button
                              onClick={() => {
                                setSelectedAtomKey(null)
                                setSelectedQuoteToHighlight(evList[0].quote)
                                setActiveDrawerTab('cv_asli')
                              }}
                              className="text-indigo-600 hover:text-indigo-800 font-medium text-[10px] mt-1 flex items-center space-x-1"
                            >
                              <span>Lihat dan sorot di naskah CV</span>
                              <ExternalLink className="w-2.5 h-2.5" />
                            </button>
                          </div>
                        ) : (
                          <p className="text-[11px] text-slate-400 italic mt-1">Tidak ada kutipan bukti yang mendukung di berkas.</p>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}

              {/* Tab 3: Berkas CV & Highlight Kutipan */}
              {activeDrawerTab === 'cv_asli' && (
                <div className="space-y-3">
                  <div className="bg-slate-100 p-2.5 rounded-lg border border-slate-200 text-xs flex items-center justify-between">
                    <span>Penampil Teks Asli Berkas: <strong>{selectedCandidate.file_name}</strong></span>
                    {(selectedQuoteToHighlight || selectedAtomKey) && (
                      <span className="bg-amber-100 text-amber-800 px-2 py-0.5 rounded text-[11px] font-bold">
                        Menyorot Kutipan Terpilih
                      </span>
                    )}
                  </div>
                  {selectedCandidate.full_text ? (
                    <CvTextViewer
                      text={selectedCandidate.full_text}
                      highlights={selectedCandidate.source_highlights || []}
                      focusKey={selectedAtomKey}
                      fallbackQuote={selectedQuoteToHighlight}
                    />
                  ) : (
                    <div className="p-4 border border-dashed border-slate-300 rounded-xl text-xs text-slate-500">
                      Teks berkas tidak tersedia untuk kandidat ini, jadi kutipan tidak dapat disorot di naskah. Ini bisa terjadi pada hasil lama
                      atau berkas tanpa lapisan teks (hasil scan gambar).
                    </div>
                  )}
                </div>
              )}

              {/* Tab 4: Riwayat & Keputusan */}
              {activeDrawerTab === 'riwayat' && (
                <div className="space-y-4 text-xs">
                  <div className="bg-white p-4 border border-slate-200 rounded-xl space-y-3">
                    <h4 className="font-bold text-slate-900">Catatan & Keputusan Hiring Manager</h4>
                    <div>
                      <label className="block text-slate-600 font-medium mb-1">Status Keputusan</label>
                      <select
                        value={selectedCandidate.decision || 'NONE'}
                        onChange={(e) => handleDecision(selectedCandidate.cv_id, e.target.value as any)}
                        className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs"
                      >
                        <option value="NONE">- Belum Diputuskan -</option>
                        <option value="SHORTLIST">Disarankan Shortlist untuk Interview</option>
                        <option value="HOLD">Tahan (Simpan di Talent Pool)</option>
                        <option value="TIDAK_LANJUT">Tidak Lanjut Tahap Ini</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-slate-600 font-medium mb-1">Catatan Tambahan</label>
                      <textarea
                        rows={3}
                        placeholder="Tambahkan catatan pertimbangan keputusan..."
                        className="w-full px-3 py-2 border border-slate-300 rounded-lg text-xs"
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Drawer Footer Actions */}
            <div className="p-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
              <span className="text-xs text-slate-500">
                Keputusan Saat Ini: <strong>{selectedCandidate.decision || 'Belum Ditentukan'}</strong>
              </span>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => handleDecision(selectedCandidate.cv_id, 'TIDAK_LANJUT')}
                  className="px-3.5 py-1.5 bg-white border border-slate-300 hover:bg-slate-100 text-slate-700 text-xs font-semibold rounded-lg transition-colors"
                >
                  Tidak Lanjut
                </button>
                <button
                  onClick={() => handleDecision(selectedCandidate.cv_id, 'HOLD')}
                  className="px-3.5 py-1.5 bg-amber-500 hover:bg-amber-600 text-white text-xs font-semibold rounded-lg transition-colors"
                >
                  Tahan
                </button>
                <button
                  onClick={() => handleDecision(selectedCandidate.cv_id, 'SHORTLIST')}
                  className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-lg shadow-xs transition-colors"
                >
                  Shortlist
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================== */}
      {/* MODAL: Bandingkan Kandidat (Side-by-side)                       */}
      {/* ============================================================== */}
      {isCompareOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/50 backdrop-blur-2xs flex items-center justify-center p-6">
          <div className="bg-white rounded-2xl max-w-4xl w-full p-6 shadow-2xl border border-slate-200 space-y-4 max-h-[90vh] flex flex-col">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-base font-bold text-slate-900">Perbandingan Kandidat Berdampingan</h3>
                <p className="text-xs text-slate-500">Menganalisis perbandingan pemenuhan kriteria antara kandidat terpilih.</p>
              </div>
              <button onClick={() => setIsCompareOpen(false)} className="text-slate-400 hover:text-slate-600 font-bold text-lg">✕</button>
            </div>

            <div className="overflow-x-auto flex-1">
              <table className="w-full text-left text-xs border border-slate-200 rounded-lg">
                <thead className="bg-slate-100 text-slate-700 font-semibold border-b border-slate-200">
                  <tr>
                    <th className="py-2.5 px-3 w-40">Kriteria</th>
                    {selectedForCompare.map((cid) => {
                      const cand = candidates.find((c) => c.cv_id === cid)
                      return (
                        <th key={cid} className="py-2.5 px-3 text-center border-l border-slate-200">
                          <p className="font-bold text-slate-900">{blindMode && !cand?.revealed ? cand?.blind_id : cand?.real_name}</p>
                          <span className="text-[10px] text-slate-500 font-mono font-normal">Skor: {cand?.final_score.toFixed(1)} (Band {cand?.band})</span>
                        </th>
                      )
                    })}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {requirements.map((r) => (
                    <tr key={r.requirement_id} className="hover:bg-slate-50">
                      <td className="py-2.5 px-3 font-medium text-slate-800">
                        <span className="font-mono text-indigo-700 font-bold mr-1">{r.requirement_id}</span>
                        {r.description}
                      </td>
                      {selectedForCompare.map((cid) => {
                        const cand = candidates.find((c) => c.cv_id === cid)
                        const st = cand?.requirement_states[r.requirement_id] || 'NOT_DEMONSTRATED'
                        return (
                          <td key={cid} className="py-2.5 px-3 text-center border-l border-slate-200">
                            <span
                              className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                st === 'STRONG'
                                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                  : st === 'PARTIAL'
                                  ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                  : 'bg-slate-100 text-slate-500'
                              }`}
                            >
                              {st === 'STRONG' ? 'Terbukti' : st === 'PARTIAL' ? 'Sebagian' : 'Tidak Tercantum'}
                            </span>
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="pt-3 border-t border-slate-100 flex justify-end">
              <button
                onClick={() => setIsCompareOpen(false)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg"
              >
                Tutup
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================== */}
      {/* MODAL: Export Data                                             */}
      {/* ============================================================== */}
      {isExportOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-2xs flex items-center justify-center p-6">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-slate-200 space-y-4">
            <h3 className="text-base font-bold text-slate-900">Export Laporan Pemeringkatan</h3>
            <p className="text-xs text-slate-500">Pilih format berkas dan cakupan data yang akan diunduh.</p>

            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-700 font-semibold mb-1">Format Berkas</label>
                <div className="flex space-x-3">
                  <label className="flex items-center space-x-1.5 cursor-pointer">
                    <input type="radio" name="fmt" defaultChecked className="text-indigo-600" />
                    <span>Excel (.XLSX)</span>
                  </label>
                  <label className="flex items-center space-x-1.5 cursor-pointer">
                    <input type="radio" name="fmt" className="text-indigo-600" />
                    <span>CSV (.CSV)</span>
                  </label>
                </div>
              </div>

              <div>
                <label className="block text-slate-700 font-semibold mb-1">Cakupan Kandidat</label>
                <select className="w-full px-3 py-2 border border-slate-300 rounded-lg">
                  <option>Semua Kandidat ({candidates.length})</option>
                  <option>Kandidat Band A & B Saja</option>
                  <option>Hanya Kandidat yang Di-shortlist</option>
                </select>
              </div>

              <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200 text-[11px] text-slate-600">
                ℹ️ Saat <strong>Blind Mode</strong> aktif, nama dan kontak disembunyikan dalam laporan ekspor sesuai regulasi privasi.
              </div>
            </div>

            <div className="flex items-center justify-end space-x-2 pt-3 border-t border-slate-100">
              <button
                onClick={() => setIsExportOpen(false)}
                className="px-4 py-2 text-slate-600 hover:text-slate-800 text-xs font-semibold"
              >
                Batal
              </button>
              <button
                onClick={() => {
                  alert('Laporan berhasil di-export sesuai format yang dipilih.')
                  setIsExportOpen(false)
                }}
                className="px-5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold rounded-lg shadow-xs"
              >
                Unduh Berkas
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
