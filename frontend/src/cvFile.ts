// The applicant's original CV file, as the recruiter's detail page describes and opens it.

export type CvInfo = { filename: string; size_bytes: number; content_type: string }

export function formatSize(bytes: number) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return Math.round(bytes / 1024) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

/** A PDF can be shown by the browser; a Word file can only be saved. */
export const cvAction = (contentType: string): 'open' | 'download' => contentType === 'application/pdf' ? 'open' : 'download'

export const cvCaption = (cv: CvInfo) => cv.filename + ' · ' + formatSize(cv.size_bytes)
