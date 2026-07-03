import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import { configureAuth } from './auth/config'
import '@aws-amplify/ui-react/styles.css'
import './styles.css'

configureAuth()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
