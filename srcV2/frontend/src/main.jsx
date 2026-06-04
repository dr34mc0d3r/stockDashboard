import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import './index.css'
import App from './App.jsx'
import Stage1Data from './pages/Stage1Data.jsx'
import Stage2Lstm from './pages/Stage2Lstm.jsx'
import Stage3MultiTask from './pages/Stage3MultiTask.jsx'
import Stage4Sentiment from './pages/Stage4Sentiment.jsx'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<App />}>
          <Route index element={<Navigate to="/stage/1" replace />} />
          <Route path="/stage/1" element={<Stage1Data />} />
          <Route path="/stage/2" element={<Stage2Lstm />} />
          <Route path="/stage/3" element={<Stage3MultiTask />} />
          <Route path="/stage/4" element={<Stage4Sentiment />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)
