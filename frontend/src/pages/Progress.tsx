// Progress.tsx
import React, { useState, useEffect } from 'react';
import { RefreshCw, CheckCircle, AlertCircle, Clock, User } from 'lucide-react';

interface Profile {
  id: string;
  name: string;
  url: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  message?: string;
}

function Progress() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [isDone, setIsDone] = useState(false);
  const [csvFilePath, setCsvFilePath] = useState<string | null>(null);

  // NEW: how many did the user *ask for*
  const [profilesNeeded, setProfilesNeeded] = useState(0);

  const [isLoading, setIsLoading] = useState(false);

  // counters
const completedCount = profiles.filter((p) => p.status === 'completed').length;
const processingCount = profiles.filter((p) => p.status === 'processing').length;
const pendingCount = profilesNeeded - (completedCount + processingCount); 
const failedCount = profiles.filter((p) => p.status === 'failed').length;

  const getStatusIcon = (status: Profile['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'processing':
        return <RefreshCw className="w-5 h-5 text-blue-500 animate-spin" />;
      case 'pending':
        return <Clock className="w-5 h-5 text-gray-500" />;
      case 'failed':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
    }
  };

  const getStatusBadgeColor = (status: Profile['status']) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'processing':
        return 'bg-blue-100 text-blue-800';
      case 'pending':
        return 'bg-gray-100 text-gray-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
    }
  };

  useEffect(() => {
    const fetchProgress = async () => {
      setIsLoading(true);
      try {
        const resp = await fetch('http://localhost:8000/api/progress');
        const data = await resp.json();
        // data: { profiles: [...], is_done: boolean, profiles_needed: number }

        if (Array.isArray(data.profiles)) {
          setProfiles(data.profiles);
        }
        if (typeof data.is_done === 'boolean') {
          setIsDone(data.is_done);
        }
        // set how many user *asked for*
        if (typeof data.profiles_needed === 'number') {
          setProfilesNeeded(data.profiles_needed);
        }
        if (data.csv_file_path) {
          setCsvFilePath(data.csv_file_path);
        }
      } catch (err) {
        console.error('Error fetching progress:', err);
      } finally {
        setIsLoading(false);
      }
    };

    // initial fetch
    fetchProgress();
    // poll every 5s
    const intervalId = setInterval(fetchProgress, 10000);
    return () => clearInterval(intervalId);
  }, []);

  // For convenience: how many have we actually discovered so far
  const discoveredCount = profiles.length; 

  return (
    <div className="space-y-6">
      {/* 1) Top bar */}
      <div className="flex items-center justify-between bg-white rounded-lg shadow-md p-4">
        {isDone ? (
          <h2 className="text-xl font-semibold">All Done!</h2>
        ) : (
          <h2 className="text-xl font-semibold">Networking Progress</h2>
        )}

        {isDone ? (
          <span className="text-green-600 font-bold">Done!</span>
        ) : isLoading ? (
          <span className="text-gray-500">Loading updates...</span>
        ) : (
          <span className="text-blue-500">Collecting data...</span>
        )}
      </div>

      {/* 2) In-progress or done message */}
      {!isDone ? (
        <div className="bg-blue-50 border border-blue-200 p-4 rounded-md text-blue-800">
          {/* Example: “In processing (2 found out of 5 needed) ...” */}
          In processing... found <strong>{discoveredCount}</strong> out of
          {' '}
          <strong>{profilesNeeded}</strong> requested.
        </div>
        
      ) : (
        <div className="bg-green-50 border border-green-200 p-4 rounded-md text-green-800">
          Hooray! All pages processed and all profiles are done.
        </div>
      )}
      {/* Add connection requests link */}
      {profiles.some(p => p.status === 'completed') && (
        <div className="bg-gray-50 border border-gray-200 p-4 rounded-md mt-4">
          <div className="flex items-center text-gray-700">
            <User className="h-5 w-5 mr-2" />
            <span>
              View your sent connection requests in{' '}
              <a 
                href="https://www.linkedin.com/mynetwork/invitation-manager/sent/" 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-blue-600 hover:text-blue-800 underline"
              >
                LinkedIn's invitation manager
              </a>
            </span>
          </div>
        </div>
      )}

      {/* Display CSV Path */}
{csvFilePath && (
  <div className="bg-gray-50 border border-gray-200 p-4 rounded-md">
    <div className="text-gray-700 mb-2">
      {isDone
        ? "Profiles have been processed. CSV file is ready for download."
        : "Profiles are being processed. You will find the in-progress CSV in the linkedin_searches directory at:"}
    </div>
    <code className="block bg-gray-100 p-3 rounded font-mono text-sm break-all text-gray-800">
      {csvFilePath}
    </code>
    {!isDone && (
      <div className="text-gray-500 text-sm mt-2 italic">
        This file is updated as each profile is processed.
      </div>
    )}

    {/* Move the download button here */}
    <div className="mt-4">
      <a
        href={`http://localhost:8000/api/download-results`}
        className={`bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 ${!isDone ? 'opacity-50 cursor-not-allowed' : ''}`}
        download
        onClick={(e) => {
          if (!isDone) e.preventDefault();
        }}
      >
        Download CSV
      </a>
      {!isDone && (
        <p className="text-sm text-gray-500 mt-2">
          The download will be available once processing is complete.
        </p>
      )}
    </div>
  </div>
)}


      {/* 3) Quick stats */}
      <div className="bg-white rounded-lg shadow-md p-6 grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-green-50 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <span className="text-green-600 font-medium">Completed</span>
            <span className="text-2xl font-bold text-green-600">
              {completedCount}
            </span>
          </div>
        </div>
        <div className="bg-blue-50 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <span className="text-blue-600 font-medium">Processing</span>
            <span className="text-2xl font-bold text-blue-600">
              {processingCount}
            </span>
          </div>
        </div>
        <div className="bg-gray-50 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <span className="text-gray-600 font-medium">Pending</span>
            <span className="text-2xl font-bold text-gray-600">
              {pendingCount}
            </span>
          </div>
        </div>
        <div className="bg-red-50 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <span className="text-red-600 font-medium">Failed</span>
            <span className="text-2xl font-bold text-red-600">
              {failedCount}
            </span>
          </div>
        </div>
      </div>

      {/* 4) Profiles Table */}
      <div className="bg-white rounded-lg shadow-md overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Profile
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  LinkedIn URL
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Message
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {profiles.length === 0 && !isDone ? (
                // If we have 0 profiles so far but not done
                <tr>
                  <td colSpan={4} className="px-6 py-4 text-center text-gray-500">
                  {profilesNeeded > 0 ? 
          `Searching for ${profilesNeeded} profiles...` : 
          'Initializing search...'}
                  </td>
                </tr>
              ) : (
                profiles.map((profile) => (
                  <tr key={profile.id} className="hover:bg-gray-50">
                    <td className="px-4 py-4">
                      <div className="flex items-center">
                        <div className="h-8 w-8 rounded-full bg-gray-100 flex items-center justify-center">
                          <User className="h-4 w-4 text-gray-400" />
                        </div>
                        <div className="ml-3">
                          <div className="text-sm font-medium text-gray-900 truncate max-w-[200px]" title={profile.name || 'No name'}>
                            {profile.name || 'No name'}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <div className="text-sm text-blue-600 hover:text-blue-800">
                        <a 
                          href={profile.url} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="block truncate max-w-[300px]"
                          title={profile.url}
                        >
                          {profile.url}
                        </a>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex items-center space-x-1">
                        {getStatusIcon(profile.status)}
                        <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusBadgeColor(profile.status)}`}>
                          {profile.status.charAt(0).toUpperCase() + profile.status.slice(1)}
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <div className="text-sm text-gray-500 truncate max-w-[200px]" title={profile.message || '-'}>
                        {profile.message || '-'}
                      </div>
                    </td>
                  </tr>
                ))
              )}

              {/* If done & no profiles => show fallback */}
              {isDone && profiles.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-6 py-4 text-center text-gray-500">
                    No profiles found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default Progress;
