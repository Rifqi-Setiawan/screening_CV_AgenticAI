// Server validation errors (FastAPI / pydantic) come in English with a raw field name. These helpers turn the common ones into
// Indonesian sentences for the applicant. Messages the server already wrote in Indonesian pass through unchanged.

export type Issue = { loc: string[]; msg: string }

const fieldLabels: Record<string, string> = {
  consent: 'Persetujuan', email: 'Email', password: 'Kata sandi', full_name: 'Nama lengkap', phone: 'Nomor telepon',
}

const rules: [RegExp, (match: RegExpMatchArray, label: string) => string][] = [
  [/^Input should be True/i, (_, label) => label + ' wajib dicentang.'],
  [/^Field required/i, (_, label) => label + ' wajib diisi.'],
  [/^String should have at least (\d+) characters?/i, (match, label) => label + ' minimal ' + match[1] + ' karakter.'],
  [/^String should have at most (\d+) characters?/i, (match, label) => label + ' maksimal ' + match[1] + ' karakter.'],
  [/valid email address/i, (_, label) => label + ' tidak valid. Gunakan alamat email yang aktif.'],
  [/^Input should be a valid (?:number|integer)/i, (_, label) => label + ' harus berupa angka.'],
]

function describeIssue(issue: Issue): string {
  const field = issue.loc.slice(1).join('.')
  const label = fieldLabels[field] ?? field
  for (const [pattern, say] of rules) {
    const match = issue.msg.match(pattern)
    if (match && label) return say(match, label)
  }
  return label ? label + ': ' + issue.msg : issue.msg
}

export const describeDetail = (detail: Issue[]) => detail.map(describeIssue).join(' ')
