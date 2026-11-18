import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import ApplicantPortal from './ApplicantPortal'
import StaffPortal from './StaffPortal'

const path = window.location.pathname
const applyPath = /^\/apply\/([^/]+)\/?$/.exec(path)
const applicantArea = applyPath !== null || /^\/pelamar\/?$/.test(path)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {applicantArea ? <ApplicantPortal jobId={applyPath ? decodeURIComponent(applyPath[1]) : null} /> : <StaffPortal />}
  </StrictMode>,
)
