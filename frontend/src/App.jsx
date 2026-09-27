import { useState } from 'react'
import Sidebar from './components/Sidebar'
import FileUpload from './components/FileUpload'
import ChatWindow from './components/ChatWindow'
import './App.css'
import QuizGenerator from './components/QuizGenerator'

function App() {
  const [activePage, setActivePage] = useState('Upload')

  return (
     <div className="app">
      <Sidebar activePage={activePage} onNavigate={setActivePage} />
      <main className="app__content">
        <h1 className="app__title">Study Notes Assistant</h1>
        <p className="app__subtitle">You're viewing: {activePage}</p>
        {activePage === 'Upload' && <FileUpload />}
        {activePage === 'Chat' && <ChatWindow />}
        {activePage === 'Quiz' && <QuizGenerator />}
      </main>
    </div>
  )
}

export default App