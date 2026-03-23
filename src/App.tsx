import React, { useState, useEffect, useMemo } from 'react';
import { 
  collection, 
  query, 
  orderBy, 
  onSnapshot, 
  addDoc, 
  updateDoc, 
  doc, 
  setDoc, 
  getDoc, 
  Timestamp, 
  where 
} from 'firebase/firestore';
import { 
  signInWithPopup, 
  GoogleAuthProvider, 
  onAuthStateChanged, 
  signOut, 
  User as FirebaseUser 
} from 'firebase/auth';
import { db, auth, OperationType, handleFirestoreError } from './firebase';
import { Incident, UserProfile, Severity, Status, Comment, UserRole } from './types';
import { analyzeIncident, generateIncidentSummary } from './services/geminiService';
import { 
  Shield, 
  AlertTriangle, 
  CheckCircle, 
  Clock, 
  Plus, 
  LogOut, 
  User as UserIcon, 
  MessageSquare, 
  ChevronRight, 
  Filter, 
  Search,
  Activity,
  BarChart3,
  MapPin,
  Info
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import Markdown from 'react-markdown';

// --- Components ---

const SeverityBadge = ({ severity }: { severity: Severity }) => (
  <span className={`severity-badge severity-${severity}`}>
    {severity}
  </span>
);

const StatusBadge = ({ status }: { status: Status }) => (
  <span className="status-badge">
    {status.replace('-', ' ')}
  </span>
);

const ErrorBoundary = ({ children }: { children: React.ReactNode }) => {
  const [hasError, setHasError] = useState(false);
  const [errorInfo, setErrorInfo] = useState<string | null>(null);

  useEffect(() => {
    const handleError = (event: ErrorEvent) => {
      if (event.error?.message?.includes('{"error":')) {
        setHasError(true);
        setErrorInfo(event.error.message);
      }
    };
    window.addEventListener('error', handleError);
    return () => window.removeEventListener('error', handleError);
  }, []);

  if (hasError) {
    return (
      <div className="p-8 bg-red-50 border-2 border-red-500 m-4">
        <h2 className="text-red-700 font-bold mb-2 uppercase tracking-widest">Security/System Error</h2>
        <p className="text-red-600 mb-4 font-mono text-sm">A critical error occurred while interacting with the database.</p>
        <pre className="bg-black text-red-400 p-4 text-xs overflow-auto max-h-64">
          {JSON.stringify(JSON.parse(errorInfo || '{}'), null, 2)}
        </pre>
        <button 
          onClick={() => window.location.reload()}
          className="mt-4 btn-primary bg-red-700 border-red-700"
        >
          Reload Application
        </button>
      </div>
    );
  }

  return <>{children}</>;
};

// --- Main App ---

export default function App() {
  const [user, setUser] = useState<FirebaseUser | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<'dashboard' | 'report' | 'detail'>('dashboard');
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [summary, setSummary] = useState<string>('');
  const [isSummarizing, setIsSummarizing] = useState(false);

  // Filters
  const [filterSeverity, setFilterSeverity] = useState<Severity | 'all'>('all');
  const [filterStatus, setFilterStatus] = useState<Status | 'all'>('all');
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (u) => {
      setUser(u);
      if (u) {
        // Fetch or create profile
        try {
          const profileDoc = await getDoc(doc(db, 'users', u.uid));
          if (profileDoc.exists()) {
            setProfile(profileDoc.data() as UserProfile);
          } else {
            const newProfile: UserProfile = {
              uid: u.uid,
              email: u.email || '',
              displayName: u.displayName,
              role: 'reporter', // Default role
              createdAt: Timestamp.now()
            };
            await setDoc(doc(db, 'users', u.uid), newProfile);
            setProfile(newProfile);
          }
        } catch (error) {
          handleFirestoreError(error, OperationType.GET, `users/${u.uid}`);
        }
      } else {
        setProfile(null);
      }
      setLoading(false);
    });
    return unsubscribe;
  }, []);

  useEffect(() => {
    if (!user) return;

    const q = query(collection(db, 'incidents'), orderBy('createdAt', 'desc'));
    const unsubscribe = onSnapshot(q, (snapshot) => {
      const data = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() } as Incident));
      setIncidents(data);
    }, (error) => {
      handleFirestoreError(error, OperationType.LIST, 'incidents');
    });

    return unsubscribe;
  }, [user]);

  useEffect(() => {
    if (!selectedIncident) return;

    const q = query(
      collection(db, 'incidents', selectedIncident.id, 'comments'), 
      orderBy('createdAt', 'asc')
    );
    const unsubscribe = onSnapshot(q, (snapshot) => {
      const data = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() } as Comment));
      setComments(data);
    }, (error) => {
      handleFirestoreError(error, OperationType.LIST, `incidents/${selectedIncident.id}/comments`);
    });

    return unsubscribe;
  }, [selectedIncident]);

  const handleLogin = async () => {
    const provider = new GoogleAuthProvider();
    try {
      await signInWithPopup(auth, provider);
    } catch (error) {
      console.error("Login error:", error);
    }
  };

  const handleLogout = () => signOut(auth);

  const handleReportIncident = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!user || !profile) return;

    const formData = new FormData(e.currentTarget);
    const title = formData.get('title') as string;
    const description = formData.get('description') as string;
    const severity = formData.get('severity') as Severity;
    const category = formData.get('category') as string;

    const newIncident = {
      title,
      description,
      severity,
      status: 'open' as Status,
      category,
      reporterUid: user.uid,
      reporterName: profile.displayName || user.email || 'Anonymous',
      createdAt: Timestamp.now(),
      updatedAt: Timestamp.now(),
    };

    try {
      await addDoc(collection(db, 'incidents'), newIncident);
      setView('dashboard');
    } catch (error) {
      handleFirestoreError(error, OperationType.CREATE, 'incidents');
    }
  };

  const handleAddComment = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!user || !profile || !selectedIncident) return;

    const formData = new FormData(e.currentTarget);
    const text = formData.get('text') as string;

    const newComment = {
      incidentId: selectedIncident.id,
      text,
      authorUid: user.uid,
      authorName: profile.displayName || user.email || 'Anonymous',
      createdAt: Timestamp.now()
    };

    try {
      await addDoc(collection(db, 'incidents', selectedIncident.id, 'comments'), newComment);
      e.currentTarget.reset();
    } catch (error) {
      handleFirestoreError(error, OperationType.CREATE, `incidents/${selectedIncident.id}/comments`);
    }
  };

  const handleUpdateStatus = async (incidentId: string, newStatus: Status) => {
    try {
      await updateDoc(doc(db, 'incidents', incidentId), {
        status: newStatus,
        updatedAt: Timestamp.now()
      });
    } catch (error) {
      handleFirestoreError(error, OperationType.UPDATE, `incidents/${incidentId}`);
    }
  };

  const generateSummary = async () => {
    if (incidents.length === 0) return;
    setIsSummarizing(true);
    const text = await generateIncidentSummary(incidents);
    setSummary(text || '');
    setIsSummarizing(false);
  };

  const filteredIncidents = useMemo(() => {
    return incidents.filter(i => {
      const matchesSeverity = filterSeverity === 'all' || i.severity === filterSeverity;
      const matchesStatus = filterStatus === 'all' || i.status === filterStatus;
      const matchesSearch = i.title.toLowerCase().includes(searchQuery.toLowerCase()) || 
                            i.description.toLowerCase().includes(searchQuery.toLowerCase());
      return matchesSeverity && matchesStatus && matchesSearch;
    });
  }, [incidents, filterSeverity, filterStatus, searchQuery]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen font-mono uppercase">
        <Activity className="animate-pulse mr-2" /> Initializing Aegis...
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex flex-col items-center justify-center h-screen p-4">
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="max-w-md w-full text-center"
        >
          <Shield className="w-16 h-16 mx-auto mb-6" />
          <h1 className="text-4xl font-bold mb-2 tracking-tighter uppercase italic">Aegis</h1>
          <p className="text-sm opacity-60 mb-8 font-mono uppercase tracking-widest">Incident Intelligence Platform</p>
          <button onClick={handleLogin} className="btn-primary w-full py-4 flex items-center justify-center gap-2">
            <UserIcon size={18} /> Authenticate with Google
          </button>
        </motion.div>
      </div>
    );
  }

  return (
    <ErrorBoundary>
      <div className="min-h-screen flex flex-col">
        {/* Header */}
        <header className="border-b border-black p-4 flex items-center justify-between sticky top-0 bg-[#E4E3E0] z-10">
          <div className="flex items-center gap-4">
            <h1 className="text-xl font-bold tracking-tighter uppercase italic cursor-pointer" onClick={() => setView('dashboard')}>
              Aegis
            </h1>
            <div className="hidden md:flex items-center gap-2 text-[10px] font-mono uppercase opacity-50">
              <Activity size={12} className="text-green-600" /> System Active
              <span className="mx-2">/</span>
              <BarChart3 size={12} /> {incidents.length} Records
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right hidden sm:block">
              <div className="text-[10px] font-mono uppercase opacity-50">{profile?.role}</div>
              <div className="text-xs font-medium">{user.displayName}</div>
            </div>
            <button onClick={handleLogout} className="btn-secondary p-2">
              <LogOut size={16} />
            </button>
          </div>
        </header>

        <main className="flex-1 p-4 md:p-8 max-w-7xl mx-auto w-full">
          <AnimatePresence mode="wait">
            {view === 'dashboard' && (
              <motion.div 
                key="dashboard"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="space-y-8"
              >
                {/* Summary Section */}
                <div className="border border-black p-6 bg-white/30">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="col-header">Executive Summary</h2>
                    <button 
                      onClick={generateSummary} 
                      disabled={isSummarizing}
                      className="text-[10px] font-mono uppercase underline hover:opacity-100 opacity-50 flex items-center gap-1"
                    >
                      {isSummarizing ? 'Analyzing...' : 'Regenerate Analysis'}
                    </button>
                  </div>
                  <div className="text-sm leading-relaxed font-serif italic opacity-80 markdown-body">
                    {summary ? (
                      <Markdown>{summary}</Markdown>
                    ) : (
                      "Click 'Regenerate Analysis' to get an AI-powered overview of current incidents."
                    )}
                  </div>
                </div>

                {/* Controls */}
                <div className="flex flex-col md:flex-row gap-4 items-end justify-between">
                  <div className="flex flex-wrap gap-4 items-center w-full md:w-auto">
                    <div className="relative flex-1 md:w-64">
                      <Search className="absolute left-3 top-1/2 -translate-y-1/2 opacity-30" size={14} />
                      <input 
                        type="text" 
                        placeholder="SEARCH INCIDENTS..." 
                        className="input-field pl-10 text-xs font-mono uppercase"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                      />
                    </div>
                    <select 
                      className="input-field text-xs font-mono uppercase w-auto"
                      value={filterSeverity}
                      onChange={(e) => setFilterSeverity(e.target.value as any)}
                    >
                      <option value="all">All Severities</option>
                      <option value="critical">Critical</option>
                      <option value="high">High</option>
                      <option value="medium">Medium</option>
                      <option value="low">Low</option>
                    </select>
                    <select 
                      className="input-field text-xs font-mono uppercase w-auto"
                      value={filterStatus}
                      onChange={(e) => setFilterStatus(e.target.value as any)}
                    >
                      <option value="all">All Statuses</option>
                      <option value="open">Open</option>
                      <option value="in-progress">In Progress</option>
                      <option value="resolved">Resolved</option>
                      <option value="closed">Closed</option>
                    </select>
                  </div>
                  <button onClick={() => setView('report')} className="btn-primary flex items-center gap-2 whitespace-nowrap">
                    <Plus size={16} /> New Report
                  </button>
                </div>

                {/* Incident List */}
                <div className="border-t border-black">
                  <div className="data-row bg-black/5 pointer-events-none">
                    <div className="col-header">ID</div>
                    <div className="col-header">Incident Title</div>
                    <div className="col-header">Severity</div>
                    <div className="col-header">Status</div>
                    <div className="col-header">Created</div>
                  </div>
                  {filteredIncidents.length > 0 ? (
                    filteredIncidents.map((incident, idx) => (
                      <div 
                        key={incident.id} 
                        className="data-row"
                        onClick={() => {
                          setSelectedIncident(incident);
                          setView('detail');
                        }}
                      >
                        <div className="data-value opacity-30 text-[10px]">{String(idx + 1).padStart(2, '0')}</div>
                        <div className="font-medium truncate pr-4">{incident.title}</div>
                        <div><SeverityBadge severity={incident.severity} /></div>
                        <div><StatusBadge status={incident.status} /></div>
                        <div className="data-value text-[10px] opacity-50">
                          {incident.createdAt.toDate().toLocaleDateString()}
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="p-12 text-center opacity-30 font-mono uppercase text-xs">
                      No matching records found.
                    </div>
                  )}
                </div>
              </motion.div>
            )}

            {view === 'report' && (
              <motion.div 
                key="report"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="max-w-2xl mx-auto"
              >
                <div className="flex items-center justify-between mb-8">
                  <h2 className="text-2xl font-bold uppercase tracking-tighter italic">New Incident Report</h2>
                  <button onClick={() => setView('dashboard')} className="btn-secondary">Cancel</button>
                </div>
                <form onSubmit={handleReportIncident} className="space-y-6 border border-black p-8 bg-white/50">
                  <div className="space-y-1">
                    <label className="col-header">Incident Title</label>
                    <input name="title" required className="input-field" placeholder="Brief summary of the issue" />
                  </div>
                  <div className="space-y-1">
                    <label className="col-header">Detailed Description</label>
                    <textarea name="description" required rows={5} className="input-field" placeholder="Provide as much detail as possible..." />
                  </div>
                  <div className="grid grid-cols-2 gap-6">
                    <div className="space-y-1">
                      <label className="col-header">Initial Severity</label>
                      <select name="severity" className="input-field">
                        <option value="low">Low</option>
                        <option value="medium">Medium</option>
                        <option value="high">High</option>
                        <option value="critical">Critical</option>
                      </select>
                    </div>
                    <div className="space-y-1">
                      <label className="col-header">Category</label>
                      <input name="category" className="input-field" placeholder="e.g. Security, Infra" />
                    </div>
                  </div>
                  <div className="pt-4">
                    <button type="submit" className="btn-primary w-full py-3">Submit Report</button>
                  </div>
                </form>
              </motion.div>
            )}

            {view === 'detail' && selectedIncident && (
              <motion.div 
                key="detail"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="grid grid-cols-1 lg:grid-cols-3 gap-8"
              >
                <div className="lg:col-span-2 space-y-8">
                  <div className="flex items-center justify-between">
                    <button onClick={() => setView('dashboard')} className="btn-secondary flex items-center gap-2">
                      <ChevronRight className="rotate-180" size={16} /> Back
                    </button>
                    <div className="flex items-center gap-2">
                      <SeverityBadge severity={selectedIncident.severity} />
                      <StatusBadge status={selectedIncident.status} />
                    </div>
                  </div>

                  <div className="space-y-4">
                    <h2 className="text-4xl font-bold tracking-tighter uppercase italic">{selectedIncident.title}</h2>
                    <div className="flex flex-wrap gap-4 text-[10px] font-mono uppercase opacity-50 border-y border-black/10 py-2">
                      <div className="flex items-center gap-1"><UserIcon size={12} /> {selectedIncident.reporterName}</div>
                      <div className="flex items-center gap-1"><Clock size={12} /> {selectedIncident.createdAt.toDate().toLocaleString()}</div>
                      <div className="flex items-center gap-1"><Info size={12} /> {selectedIncident.category}</div>
                    </div>
                    <div className="text-lg leading-relaxed font-serif opacity-80 whitespace-pre-wrap">
                      {selectedIncident.description}
                    </div>
                  </div>

                  {/* Comments */}
                  <div className="space-y-6 border-t border-black pt-8">
                    <h3 className="col-header">Communication Log</h3>
                    <div className="space-y-4">
                      {comments.map(comment => (
                        <div key={comment.id} className="border-l-2 border-black pl-4 py-2">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-[10px] font-mono uppercase font-bold">{comment.authorName}</span>
                            <span className="text-[10px] font-mono opacity-50">{comment.createdAt.toDate().toLocaleTimeString()}</span>
                          </div>
                          <p className="text-sm opacity-80">{comment.text}</p>
                        </div>
                      ))}
                    </div>
                    <form onSubmit={handleAddComment} className="flex gap-2">
                      <input name="text" required className="input-field flex-1" placeholder="Add to log..." />
                      <button type="submit" className="btn-primary">Send</button>
                    </form>
                  </div>
                </div>

                {/* Sidebar Actions */}
                <div className="space-y-6">
                  <div className="border border-black p-6 bg-white/50 space-y-6">
                    <h3 className="col-header">Incident Controls</h3>
                    
                    <div className="space-y-2">
                      <label className="text-[10px] font-mono uppercase opacity-50">Update Status</label>
                      <div className="grid grid-cols-1 gap-2">
                        {(['open', 'in-progress', 'resolved', 'closed'] as Status[]).map(s => (
                          <button 
                            key={s}
                            onClick={() => handleUpdateStatus(selectedIncident.id, s)}
                            disabled={selectedIncident.status === s}
                            className={`text-left px-3 py-2 text-xs font-mono uppercase border ${selectedIncident.status === s ? 'bg-black text-white' : 'hover:bg-black/5'}`}
                          >
                            {s.replace('-', ' ')}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="pt-4 border-t border-black/10">
                      <div className="text-[10px] font-mono uppercase opacity-50 mb-2">Location Data</div>
                      <div className="flex items-center gap-2 text-xs font-mono">
                        <MapPin size={14} /> 
                        {selectedIncident.location ? `${selectedIncident.location.latitude}, ${selectedIncident.location.longitude}` : 'No GPS Data'}
                      </div>
                    </div>
                  </div>

                  <div className="border border-black p-6 bg-black text-white space-y-4">
                    <h3 className="text-[10px] font-mono uppercase opacity-50">Intelligence Note</h3>
                    <p className="text-xs font-serif italic leading-relaxed opacity-80">
                      This incident is currently being monitored by Aegis. All communications are logged and analyzed for trend detection.
                    </p>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </main>

        {/* Footer */}
        <footer className="border-t border-black p-4 text-[10px] font-mono uppercase opacity-30 flex justify-between">
          <div>Aegis Incident Intelligence // v1.0.4</div>
          <div>{new Date().getFullYear()} © Sentinel Systems</div>
        </footer>
      </div>
    </ErrorBoundary>
  );
}
