import React, { useState } from 'react';
import { Upload, AlertCircle } from 'lucide-react';

const BrowserInstructions = () => (
  <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 h-full">
    <h3 className="text-lg font-semibold mb-4 text-yellow-800 flex items-center">
      <AlertCircle className="w-5 h-5 mr-2" />
      Browser Setup Required
    </h3>
    <p className="text-yellow-800 mb-4 text-sm">Do this before starting:</p>
    <div className="space-y-4">
      <div className="flex items-start">
        <div className="ml-2">
          <p className="text-yellow-800 text-sm">
            Use Safari or another browser to access this website (after quitting Chrome completely - make sure it's not running in background). This is to ensure the agent opens your Chrome in debug mode and the LinkedIn is logged in.
          </p>
        </div>
      </div>
    </div>
  </div>
);

function Home() {
  // Point to your FastAPI server's base URL
  const baseUrl = 'http://localhost:8000';

  // ================== States for the Resume Summary UI ===================
  const [GeminiApiKey, setGeminiApiKey] = useState('');
  const [resumeSummary, setResumeSummary] = useState<string | null>(null);
  const [isSummarizing, setIsSummarizing] = useState(false);
  const [connectionRequests, setConnectionRequests] = useState('');
  const [requestsArray, setRequestsArray] = useState<string[]>([]);
  const [templatesLocked, setTemplatesLocked] = useState(false);
  const [isEditable, setIsEditable] = useState(true);

  // ================== States for LinkedIn Automation ===================
  const [liCompanies, setLiCompanies] = useState('');
  const [liTitles, setLiTitles] = useState('');
  const [liUniversities, setLiUniversities] = useState('');
  const [liProfilesNeeded, setLiProfilesNeeded] = useState<number>(5);
  const [liAdditionalFilters, setLiAdditionalFilters] = useState('');
  const [liStatus, setLiStatus] = useState('');
  const [searchMethod, setSearchMethod] = useState('url');
  const [linkedInUrl, setLinkedInUrl] = useState('');
  const [sendConnectionRequest, setSendConnectionRequest] = useState(true);
  const [includeNote, setIncludeNote] = useState(true);
  const [templateMode, setTemplateMode] = useState<'examples' | 'custom'>('examples');
  const [selectedTemplate, setSelectedTemplate] = useState<number | null>(null);
  const [customTemplate, setCustomTemplate] = useState(
    "Hey [linkedin profile first name], \nI'm a junior at Wharton studying economics. I'm very interested in breaking into [linkedin profile industry name] and would love to chat.\nBest,\nJohn"
  );

  // Add this helper function at the top level
  const MAX_CHARS = 300;
  const isTemplateValid = (text: string) => text.length <= MAX_CHARS;

  // Add this state for tracking validation
  const [templateErrors, setTemplateErrors] = useState<{[key: number]: boolean}>({});
  const [customTemplateError, setCustomTemplateError] = useState(false);

  // Add new state for GPT API Key
  const [GPTApiKey, setGPTApiKey] = useState('');

  // ============== (A) Handle Gemini API Key Submission ==============
  const handleApiKeySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const resp = await fetch(`${baseUrl}/api/set-key`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: GeminiApiKey }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.detail || 'Error setting Gemini API key');
      }
      alert(`Key set: ${data.message}`);
    } catch (err: any) {
      alert('Failed to set key: ' + err.message);
    }
  };

  // Add new handler for GPT API Key
  const handleGPTApiKeySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const resp = await fetch(`${baseUrl}/api/set-gpt-key`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: GPTApiKey }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.detail || 'Error setting GPT API key');
      }
      alert(`Key set: ${data.message}`);
    } catch (err: any) {
      alert('Failed to set key: ' + err.message);
    }
  };

  const handleRequestChange = (newValue: string, idx: number) => {
    setRequestsArray((prev) => {
      const updated = [...prev];
      updated[idx] = newValue;
      return updated;
    });
    setTemplateErrors(prev => ({
      ...prev,
      [idx]: !isTemplateValid(newValue)
    }));
  };

  // Add this for custom template
  const handleCustomTemplateChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newValue = e.target.value;
    setCustomTemplate(newValue);
    setCustomTemplateError(!isTemplateValid(newValue));
  };

  // ============== (A) Updated function name and logic
  const handleConfirmTemplates = async () => {
    // Check if any templates exceed character limit
    if (templateMode === 'examples') {
      const hasErrors = requestsArray.some(req => !isTemplateValid(req));
      if (hasErrors) {
        alert('Please fix templates that exceed 300 character limit before confirming.');
        return;
      }
    } else {
      if (!isTemplateValid(customTemplate)) {
        alert('Please fix template that exceeds 300 character limit before confirming.');
        return;
      }
    }

    try {
      const resp = await fetch(`${baseUrl}/api/linkedin-examples`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          templates: templateMode === 'examples' ? requestsArray : [customTemplate],
          mode: templateMode 
        }),
      });
      if (!resp.ok) {
        throw new Error('Failed to submit template');
      }

      setTemplatesLocked(true);
      alert('Template confirmed and locked!');
    } catch (err: any) {
      alert('Error: ' + err.message);
    }
  };

  // ============== (B) Handle Resume File Upload + Summarize ==============
  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setIsSummarizing(true);

      const formData = new FormData();
      formData.append('file', file);

      const res = await fetch(`${baseUrl}/api/upload-cv`, {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || 'Upload failed');
      }

      const data = await res.json();
      setResumeSummary(data.summary);
      setConnectionRequests(data.connection_requests);
      
      // Parse the requests and initialize error states
      const parsedRequests = data.connection_requests
        .split('———')
        .map((req: string) => req.trim())
        .filter(Boolean);

      setRequestsArray(parsedRequests);

      // Initialize template errors for each request
      const initialErrors = parsedRequests.reduce((acc: {[key: number]: boolean}, req: string, idx: number) => {
        acc[idx] = !isTemplateValid(req);
        return acc;
      }, {});
      setTemplateErrors(initialErrors);

    } catch (err: any) {
      alert('Something went wrong while uploading/summarizing your CV: ' + err.message);
    } finally {
      setIsSummarizing(false);
    }
  };

  // ============== (C) Handle Saving Updated Summary ==============
  const handleSaveSummary = async (e: React.FormEvent) => {
    e.preventDefault();
    
    try {
      const resp = await fetch(`${baseUrl}/api/save-summary`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ summary: resumeSummary }),
      });

      if (!resp.ok) {
        throw new Error('Failed to save summary');
      }

      // Make textarea uneditable after successful save
      setIsEditable(false);
      alert('Summary saved successfully!');
    } catch (err: any) {
      alert('Error saving summary: ' + err.message);
    }
  };

  // ============== (D) Handle LinkedIn Automation ==============
  const handleLinkedInAutomation = async () => {
    try {
        const basePayload = searchMethod === 'url' 
    ? { linkedin_url: linkedInUrl, profiles_needed: liProfilesNeeded }
    : {
        companies: liCompanies,
        titles: liTitles,
        universities: liUniversities,
        profiles_needed: liProfilesNeeded,
        additional_filters: liAdditionalFilters,
      };

      const payload = {
        ...basePayload,
        send_connection_request: sendConnectionRequest,
        include_note: includeNote,
      };

      const resp = await fetch(`${baseUrl}/api/linkedin`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.detail || 'Error starting LinkedIn automation');
      }

      window.location.href = '/progress';  
      // e.g. returns: { message: "Search initiated. Check logs for details." }
      setLiStatus(`${data.message}`);
    } catch (err: any) {
      setLiStatus('Error starting search: ' + err.message);
    }
  };

  return (
    <div className="grid grid-cols-1 gap-8 md:gap-8 md:grid-cols-2 p-4">
      {/* Top Section with Getting Started and Browser Instructions */}
      <div className="col-span-2 grid md:grid-cols-2 gap-6">
        {/* Getting Started */}
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold mb-4 text-gray-800 flex items-center">
            <svg className="w-6 h-6 mr-2 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            Getting Started
          </h2>
          <ol className="space-y-3">
            {[
              "Get a free Gemini API key and save it below",
              "Upload your resume and edit the resume summary",
              "Edit and confirm the message templates",
              "Enter the LinkedIn search URL or filters",
              "Start networking!"
            ].map((step, index) => (
              <li key={index} className="flex items-start">
                <span className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-full bg-blue-100 text-blue-600 font-medium text-sm mr-3">
                  {index + 1}
                </span>
                <span className="text-gray-700 text-sm pt-1">{step}</span>
              </li>
            ))}
          </ol>
        </div>

        {/* Browser Instructions */}
        <BrowserInstructions />
      </div>

      {/* =========================================================
          1) Full-Width Top Section: Gemini API Key
      ========================================================= */}
      <div className="col-span-2 bg-white rounded-lg shadow-md p-6 mb-4">
        <h2 className="text-lg font-semibold mb-4">API Keys (save both keys for best results)</h2>
        
        {/* Gemini API Key */}
        <div className="mb-6">
          <h3 className="text-md font-medium mb-2">Gemini API Key</h3>
          <text className="block mb-4">
            You can set it up completely free on&nbsp;
            <a 
              href="https://aistudio.google.com/app/apikey"
              target="_blank" 
              rel="noopener noreferrer" 
              className="text-blue-600 underline hover:text-blue-800">
              Gemini's website
            </a>.
          </text>

          <form onSubmit={handleApiKeySubmit} className="flex items-center gap-2">
            <input
              type="text"
              value={GeminiApiKey}
              onChange={(e) => setGeminiApiKey(e.target.value)}
              placeholder="Enter your Gemini API Key..."
              className="flex-1 rounded-lg border border-gray-300 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              type="submit"
              className="bg-blue-600 text-white rounded-lg p-2 hover:bg-blue-700 transition-colors"
            >
              Save Key
            </button>
          </form>
          <p className="text-sm text-gray-600 mt-2">
            If the above doesn't work, you can set it in your terminal by running:<br/>
            <code className="bg-gray-100 px-2 py-1 rounded">export GEMINI_API_KEY=your_key_here</code>
          </p>
        </div>

        {/* GPT API Key */}
        <div>
          <h3 className="text-md font-medium mb-2">GPT API Key</h3>
          <text className="block mb-4">
            You can get your API key from&nbsp;
            <a 
              href="https://platform.openai.com/api-keys"
              target="_blank" 
              rel="noopener noreferrer" 
              className="text-blue-600 underline hover:text-blue-800">
              OpenAI's website
            </a>.
          </text>

          <form onSubmit={handleGPTApiKeySubmit} className="flex items-center gap-2">
            <input
              type="text"
              value={GPTApiKey}
              onChange={(e) => setGPTApiKey(e.target.value)}
              placeholder="Enter your GPT API Key..."
              className="flex-1 rounded-lg border border-gray-300 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              type="submit"
              className="bg-blue-600 text-white rounded-lg p-2 hover:bg-blue-700 transition-colors"
            >
              Save Key
            </button>
          </form>
          <p className="text-sm text-gray-600 mt-2">
            If the above doesn't work, you can set it in your terminal by running:<br/>
            <code className="bg-gray-100 px-2 py-1 rounded">export OPENAI_API_KEY=sk-your_key_here</code>
          </p>
        </div>
      </div>

      {/* =========================================================
          2) Left Column: Resume Upload / Summarize / Summary
      ========================================================= */}
      <div className="bg-white rounded-lg shadow-md p-6 flex flex-col h-auto">
        <h2 className="text-lg font-semibold mb-4 flex items-center">
          <Upload className="w-5 h-5 mr-2 text-blue-600" />
          {isSummarizing
            ? 'Summarizing...'
            : resumeSummary
            ? 'Resume Summary'
            : 'Upload Resume'}
        </h2>

        {/* (A) If no summary and not summarizing => show upload */}
        {!resumeSummary && !isSummarizing && (
          <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
            <input
              type="file"
              accept=".txt,.pdf,.doc,.docx"
              onChange={handleFileChange}
              className="hidden"
              id="resume-upload"
            />
            <label
              htmlFor="resume-upload"
              className="cursor-pointer inline-flex flex-col items-center"
            >
              <Upload className="w-12 h-12 text-gray-400 mb-3" />
              <span className="text-sm text-gray-600">
                Click to upload your resume
              </span>
              <span className="text-xs text-gray-500 mt-1">
                Supported formats: PDF, DOC, DOCX, TXT
              </span>
            </label>
          </div>
        )}

        {/* (B) If summarizing => show waiting message */}
        {isSummarizing && !resumeSummary && (
          <div className="flex-1 flex items-center justify-center">
            <p className="text-gray-600 italic">Summarizing your CV... Please wait.</p>
          </div>
        )}

        {/* (C) If we have summary => show text area + "Save Summary" */}
        {resumeSummary && (
          <form onSubmit={handleSaveSummary} className="flex flex-col flex-1">
            <textarea
              className={`flex-1 w-full border border-gray-300 rounded-lg p-2 focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                !isEditable ? 'bg-gray-100' : ''
              }`}
              value={resumeSummary}
              onChange={(e) => setResumeSummary(e.target.value)}
              placeholder="Your CV summary will appear here..."
              rows={10}
              readOnly={!isEditable}
            />
            <button
              type="submit"
              className="mt-4 bg-blue-600 text-white rounded-lg p-2 hover:bg-blue-700 transition-colors self-start"
            >
              Save Summary
            </button>
          </form>
        )}
      </div>

      {/* =========================================================
          3) Right Column: LinkedIn Automation
      ========================================================= */}
<div className="bg-white rounded-lg shadow-md p-6 flex flex-col h-auto">
  <h2 className="text-lg font-semibold mb-4">LinkedIn Search</h2>

  {/* Alert Message */}
  <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg flex items-start">
    <AlertCircle className="h-5 w-5 text-blue-500 mt-0.5 mr-2 flex-shrink-0" />
    <p className="text-sm text-blue-700">
      Pro tip: Using a LinkedIn search URL is faster and more accurate! Our agent is smart, but not AGI-level smart... yet 😉
    </p>
  </div>

  {/* Custom Tabs */}
  <div className="w-full mb-6">
    <div className="grid grid-cols-2 gap-2 mb-6">
      <button
        onClick={() => setSearchMethod('url')}
        className={`p-2.5 text-sm font-medium rounded-lg transition-colors
          ${searchMethod === 'url' 
            ? 'bg-blue-100 text-blue-700' 
            : 'bg-gray-50 text-gray-600 hover:bg-gray-100'}`}
      >
        Use LinkedIn URL
      </button>
      <button
        onClick={() => setSearchMethod('form')}
        className={`p-2.5 text-sm font-medium rounded-lg transition-colors
          ${searchMethod === 'form' 
            ? 'bg-blue-100 text-blue-700' 
            : 'bg-gray-50 text-gray-600 hover:bg-gray-100'}`}
      >
        Use Search Form
      </button>
    </div>

    {/* URL Input Section */}
    {searchMethod === 'url' && (
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            How to get your LinkedIn search URL:
          </label>
          <ol className="list-decimal ml-4 space-y-2 text-sm text-gray-600 mb-4">
            <li>Go to LinkedIn and search for your target role (e.g., "2nd year associate" or "IB analyst")</li>
            <li>Add your desired filters (e.g., schools: UPenn, Cornell; companies: Goldman Sachs)</li>
            <li>After applying all filters, copy the entire URL from your browser</li>
            <li>Paste the URL below (it should look similar to: https://www.linkedin.com/search/results/people/?keywords=ib%20analyst...)</li>
          </ol>
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700">
            LinkedIn Search URL
          </label>
          <input
            type="text"
            value={linkedInUrl}
            onChange={(e) => setLinkedInUrl(e.target.value)}
            placeholder="Paste your LinkedIn search URL here..."
            className="mt-1 p-2 border border-gray-300 rounded w-full"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">
            Number of Profiles Needed
          </label>
          <input
            type="number"
            value={liProfilesNeeded}
            onChange={(e) => setLiProfilesNeeded(Number(e.target.value))}
            className="mt-1 p-2 border border-gray-300 rounded w-full"
          />
        </div>
      </div>
    )}

    {/* Form Input Section */}
    {searchMethod === 'form' && (
      <div className="space-y-4">
        <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg flex items-start mb-4">
          <AlertCircle className="h-5 w-5 text-yellow-500 mt-0.5 mr-2 flex-shrink-0" />
          <p className="text-sm text-yellow-700">
            Note: Using the form method requires our AI to interpret and apply filters, which might be slower and less precise than using a direct LinkedIn URL. If you need more filters, use the URL method.
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">
            Titles (comma-separated)
          </label>
          <input
            type="text"
            value={liTitles}
            onChange={(e) => setLiTitles(e.target.value)}
            placeholder="e.g. Investment Banking Analyst, Associate"
            className={`mt-1 p-2 border ${!liTitles.trim() ? 'border-red-300' : 'border-gray-300'} rounded w-full`}
          />
          {!liTitles.trim() && (
            <p className="mt-1 text-sm text-red-500">Required field</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">
            Companies (comma-separated)
          </label>
          <input
            type="text"
            value={liCompanies}
            onChange={(e) => setLiCompanies(e.target.value)}
            placeholder="e.g. Goldman Sachs, Morgan Stanley"
            className={`mt-1 p-2 border ${!liCompanies.trim() ? 'border-red-300' : 'border-gray-300'} rounded w-full`}
          />
          {!liCompanies.trim() && (
            <p className="mt-1 text-sm text-red-500">Required field</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">
            Universities (comma-separated)
          </label>
          <input
            type="text"
            value={liUniversities}
            onChange={(e) => setLiUniversities(e.target.value)}
            placeholder="e.g. Penn State, Cornell"
            className={`mt-1 p-2 border ${!liUniversities.trim() ? 'border-red-300' : 'border-gray-300'} rounded w-full`}
          />
          {!liUniversities.trim() && (
            <p className="mt-1 text-sm text-red-500">Required field</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">
            Number of Profiles Needed
          </label>
          <input
            type="number"
            value={liProfilesNeeded}
            onChange={(e) => setLiProfilesNeeded(Number(e.target.value))}
            className={`mt-1 p-2 border ${!liProfilesNeeded ? 'border-red-300' : 'border-gray-300'} rounded w-full`}
          />
          {!liProfilesNeeded && (
            <p className="mt-1 text-sm text-red-500">Required field</p>
          )}
        </div>
      </div>
    )}
  </div>


{/* Replace the existing LinkedIn automation button section with this */}
<div className="mt-6 space-y-4">
  <div className="space-y-3">
    <div className="flex items-center">
      <label className="relative inline-flex items-center cursor-pointer">
        <input
          type="checkbox"
          checked={sendConnectionRequest}
          onChange={(e) => {
            setSendConnectionRequest(e.target.checked);
            if (!e.target.checked) setIncludeNote(false);
          }}
          className="sr-only peer"
        />
        <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
        <span className="ms-3 text-sm font-medium text-gray-700">Send connection requests</span>
      </label>
    </div>

    <div className="flex items-center">
      <label className="relative inline-flex items-center cursor-pointer">
        <input
          type="checkbox"
          checked={includeNote}
          onChange={(e) => setIncludeNote(e.target.checked)}
          disabled={!sendConnectionRequest}
          className="sr-only peer"
        />
        <div className={`w-11 h-6 ${!sendConnectionRequest ? 'bg-gray-100' : 'bg-gray-200'} peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600`}></div>
        <span className={`ms-3 text-sm font-medium ${!sendConnectionRequest ? 'text-gray-400' : 'text-gray-700'}`}>Include personalized note</span>
      </label>
    </div>
  </div>

  {/* Show warnings if requirements aren't met */}
  {sendConnectionRequest && includeNote && (isEditable || !templatesLocked) && (
    <div className="space-y-2">
      <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg flex items-start">
        <AlertCircle className="h-5 w-5 text-yellow-500 mt-0.5 mr-2 flex-shrink-0" />
        <div className="text-sm text-yellow-700">
          <p className="font-medium">Required steps before starting:</p>
          <ul className="list-disc ml-4 mt-1">
            {isEditable && <li>Save your resume summary</li>}
            {!templatesLocked && <li>Confirm your message templates</li>}
          </ul>
        </div>
      </div>
    </div>
  )}

  <button
    onClick={handleLinkedInAutomation}
    disabled={
      // Only check conditions if sending connection requests with notes
      sendConnectionRequest && includeNote && 
      // Then verify if either condition is not met
      (isEditable || !templatesLocked)
    }
    className={`px-4 py-2 rounded ${
      sendConnectionRequest && includeNote && (isEditable || !templatesLocked)
        ? 'bg-gray-400 cursor-not-allowed'
        : 'bg-blue-600 hover:bg-blue-700'
    } text-white w-full`}
  >
    Start Search
  </button>

  {liStatus && (
    <p className="mt-4 p-2 bg-gray-100 text-gray-800 rounded">
      {liStatus}
    </p>
  )}
</div>

</div>
    

    {/* First show template editing UI */}
    {resumeSummary && requestsArray.length > 0 && (
      <div className="col-span-2 bg-white rounded-lg shadow-md p-6">
        <h3 className="text-md font-semibold mb-2">
          LinkedIn Message Template (Shorten to 200 characters for free accounts, 300 characters for premium accounts)
        </h3>
  
        <div className="mb-6">
          <div className="grid grid-cols-2 gap-2 mb-4">
            <button
              onClick={() => setTemplateMode('examples')}
              className={`p-2.5 text-sm font-medium rounded-lg transition-colors
                ${templateMode === 'examples' 
                  ? 'bg-blue-100 text-blue-700' 
                  : 'bg-gray-50 text-gray-600 hover:bg-gray-100'}`}
            >
              Let AI Generate Custom Messages
            </button>
            <button
              onClick={() => setTemplateMode('custom')}
              className={`p-2.5 text-sm font-medium rounded-lg transition-colors
                ${templateMode === 'custom' 
                  ? 'bg-blue-100 text-blue-700' 
                  : 'bg-gray-50 text-gray-600 hover:bg-gray-100'}`}
            >
              Use Strict Template
            </button>
          </div>
  
          {templateMode === 'examples' ? (
            <div className="space-y-4">
              <p className="text-sm text-gray-600 mb-4">
                The AI will use these examples to learn your style and generate personalized messages:
              </p>
              {requestsArray.map((req, idx) => (
                <div
                  key={idx}
                  className="p-4 rounded-lg border border-gray-200"
                >
                  <div className="relative">
                    <textarea
                      value={req}
                      onChange={(e) => handleRequestChange(e.target.value, idx)}
                      readOnly={templatesLocked}
                      rows={4}
                      className={`w-full ${
                        templatesLocked ? 'bg-transparent' : 'bg-white'
                      } border-none focus:ring-0 ${
                        templateErrors[idx] ? 'text-red-600' : 'text-gray-900'
                      }`}
                    />
                    <div className="absolute bottom-2 right-2 text-sm">
                      <span className={`${
                        templateErrors[idx] ? 'text-red-600 font-medium' : 'text-gray-500'
                      }`}>
                        {req.length}/{MAX_CHARS}
                      </span>
                    </div>
                    {templateErrors[idx] && (
                      <p className="text-red-600 text-sm mt-1">
                        Message exceeds 300 character limit - please shorten it for LinkedIn's character limit
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-sm text-gray-600 mb-4">
                This template will be strictly followed for all messages. Use placeholders like [linkedin profile details] to refer to the profile you are messaging. For your own details, use your ACTUAL DETAILS - they will be sent as connection request notes if you choose to send connection requests.
              </p>
              <div className="relative">
                <textarea
                  value={customTemplate}
                  onChange={handleCustomTemplateChange}
                  readOnly={templatesLocked}
                  rows={6}
                  className={`w-full p-4 rounded-lg border ${
                    templatesLocked ? 'bg-gray-50' : 'bg-white'
                  } border-gray-200 ${
                    customTemplateError ? 'text-red-600 border-red-300' : 'text-gray-900'
                  }`}
                />
                <div className="absolute bottom-2 right-2 text-sm">
                  <span className={`${
                    customTemplateError ? 'text-red-600 font-medium' : 'text-gray-500'
                  }`}>
                    {customTemplate.length}/{MAX_CHARS}
                  </span>
                </div>
                {customTemplateError && (
                  <p className="text-red-600 text-sm mt-1">
                    Message exceeds 300 character limit - please shorten it for LinkedIn's character limit
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
  
        <button
          onClick={handleConfirmTemplates}
          disabled={templatesLocked}
          className={`px-4 py-2 rounded ${
            templatesLocked
              ? 'bg-gray-400 cursor-not-allowed'
              : 'bg-blue-600 hover:bg-blue-700'
          } text-white`}
        >
          Confirm Template
        </button>
      </div>
    )}


    </div>

  );
}

export default Home;
