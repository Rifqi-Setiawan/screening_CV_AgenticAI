export type Route =
  | { view: 'lowongan' }
  | { view: 'lamaran' }
  | { view: 'detail'; jobId: string; applicationId: string }

// Ids are UUIDs from the API; anything else (spaces, dots, slashes, markup) is not a route.
const idPattern = /^[\w-]{1,64}$/

/** Parse `location.hash`. A broken detail link lands on the list instead of an empty page. */
export function parseRoute(hash: string): Route {
  if (!hash.startsWith('#')) return { view: 'lowongan' }
  const [section, ...rest] = hash.slice(1).split('/')
  if (section !== 'lamaran') return { view: 'lowongan' }
  if (rest.length === 2 && rest.every(part => idPattern.test(part))) {
    return { view: 'detail', jobId: rest[0], applicationId: rest[1] }
  }
  return { view: 'lamaran' }
}

export function detailHash(jobId: string, applicationId: string): string {
  return idPattern.test(jobId) && idPattern.test(applicationId) ? '#lamaran/' + jobId + '/' + applicationId : '#lamaran'
}
