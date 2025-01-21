import React from 'react';
import { Routes, Route, Link, useLocation } from 'react-router-dom';
import { Briefcase, LayoutList } from 'lucide-react';
import Home from './pages/Home';
import Progress from './pages/Progress';

function App() {
  const location = useLocation();

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-5xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Briefcase className="w-6 h-6 text-blue-600" />
              <h1 className="text-xl font-semibold text-gray-900">LinkedOut</h1>
            </div>
            <nav className="flex space-x-4">
              <Link
                to="/"
                className={`px-4 py-2 rounded-md transition-colors ${
                  location.pathname === '/'
                    ? 'bg-blue-50 text-blue-600'
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                Home
              </Link>
              <Link
                to="/progress"
                className={`px-4 py-2 rounded-md transition-colors ${
                  location.pathname === '/progress'
                    ? 'bg-blue-50 text-blue-600'
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                <span className="flex items-center gap-1">
                  <LayoutList className="w-4 h-4" />
                  Progress
                </span>
              </Link>
            </nav>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/progress" element={<Progress />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;