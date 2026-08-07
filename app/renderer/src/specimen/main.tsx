import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '../index.css'
import { TokenSpecimen } from './TokenSpecimen'

const rootEl = document.getElementById('root')
if (!rootEl) throw new Error('#root element not found')

createRoot(rootEl).render(
  <StrictMode>
    <TokenSpecimen />
  </StrictMode>,
)
