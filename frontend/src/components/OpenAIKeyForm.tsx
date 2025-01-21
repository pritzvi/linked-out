import React, { useState } from 'react';

interface Props {
  apiBaseUrl?: string; // if you want to pass in something like http://localhost:8000
}

function OpenAIKeyForm({ apiBaseUrl = 'http://localhost:8000' }: Props) {
  const [openAiKey, setOpenAiKey] = useState('');
  const [keyMessage, setKeyMessage] = useState('');

  const handleSaveKey = async () => {
    try {
      // POST to /api/set-key with { key: openAiKey }
      const resp = await fetch(`${apiBaseUrl}/api/set-key`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: openAiKey })
      });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.detail || 'Error setting OpenAI key');
      }
      setKeyMessage(`Success: ${data.message}`);
    } catch (error: any) {
      setKeyMessage(`Error: ${error.message}`);
    }
  };

  return (
    <div className="bg-white p-4 rounded shadow-md max-w-md mb-6">
      <h2 className="text-lg font-semibold mb-2">Set Your OpenAI Key</h2>
      <div className="flex gap-2 mb-2">
        <input
          type="text"
          className="p-2 border border-gray-300 rounded w-full"
          placeholder="Enter your OpenAI API key (sk-...)"
          value={openAiKey}
          onChange={(e) => setOpenAiKey(e.target.value)}
        />
        <button
          onClick={handleSaveKey}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
        >
          Save Key
        </button>
      </div>
      {keyMessage && (
        <div className="mt-2 p-2 bg-gray-100 text-gray-800 rounded">
          {keyMessage}
        </div>
      )}
    </div>
  );
}

export default OpenAIKeyForm;
