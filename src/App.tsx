import React, { useState, useEffect, useMemo } from 'react';
import { Incident, UserProfile, Severity, Status, Comment, UserRole } from './types';
import { fetchIncidents, fetchComments, addComment, updateIncidentStatus, connectWebSocket } from './api';
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

// Mock User for MVP Dashboard
const MOCK_USER = {
  uid: "admin123",
  email: "admin@vigilinex.com",
  displayName: "Vigilinex Administrator",
  role: "admin"
};

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

export default function App() {
  const [user, setUser] = useState<any | null>(() => {
    const saved = localStorage.getItem('vigilinex_user');
    return saved ? JSON.parse(saved) : null;
  });
  const [profile, setProfile] = useState<any | null>(() => {
    const saved = localStorage.getItem('vigilinex_profile');
    return saved ? JSON.parse(saved) : null;
  });
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<'dashboard' | 'report' | 'detail'>('dashboard');
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  
  // Filters
  const [filterSeverity, setFilterSeverity] = useState<Severity | 'all'>('all');
  const [filterStatus, setFilterStatus] = useState<Status | 'all'>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const loadIncidents = async () => {
    try {
      const data = await fetchIncidents();
      setIncidents(data);
    } catch (e) {
      console.error("Failed to fetch incidents", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user) {
      loadIncidents();
      
      // Connect to Vigilinex Intelligence Stream!
      const disconnect = connectWebSocket(
        (metric) => {
          console.log("Realtime metric:", metric);
        },
        (incident) => {
          console.log("Realtime incident:", incident);
          // Prepend new incident
          setIncidents(prev => [{
            ...incident,
            createdAt: { toDate: () => new Date(incident.createdAt) },
            updatedAt: { toDate: () => new Date(incident.updatedAt) }
          }, ...prev]);
        }
      );
      
      return () => disconnect();
    }
  }, [user]);

  useEffect(() => {
    if (!selectedIncident) return;
    
    // Fetch comments
    const loadComments = async () => {
      try {
        const data = await fetchComments(selectedIncident.id);
        setComments(data);
      } catch (e) {
        console.error("Failed to load comments", e);
      }
    };
    
    loadComments();
    
    // We would ideally listen to WebSocket for comments too, but polling/refresh is ok for MVP
    const interval = setInterval(loadComments, 10000);
    return () => clearInterval(interval);
  }, [selectedIncident]);

  const handleLogin = () => {
    setUser(MOCK_USER);
    setProfile(MOCK_USER);
    localStorage.setItem('vigilinex_user', JSON.stringify(MOCK_USER));
    localStorage.setItem('vigilinex_profile', JSON.stringify(MOCK_USER));
  };

  const handleLogout = () => {
    setUser(null);
    setProfile(null);
    localStorage.removeItem('vigilinex_user');
    localStorage.removeItem('vigilinex_profile');
  };

  const handleReportIncident = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    // Post to standard FastAPI endpoint ideally. We didn't build `POST /incidents` in our backend MVP,
    // as incidents are automatically created by the Anomaly Engine!
    alert('Manual incident reporting is disabled. The Vigilinex Engine automatically creates incidents via Anomaly Detection.');
    setView('dashboard');
  };

  const handleAddComment = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!selectedIncident) return;

    const formData = new FormData(e.currentTarget);
    const text = formData.get('text') as string;

    try {
      const newComment = await addComment(selectedIncident.id, text, profile.displayName);
      setComments(prev => [...prev, newComment]);
      e.currentTarget.reset();
    } catch (error) {
      console.error("Failed to add comment", error);
    }
  };

  const handleUpdateStatus = async (incidentId: string, newStatus: Status) => {
    try {
      await updateIncidentStatus(incidentId, newStatus);
      setIncidents(prev => prev.map(i => i.id === incidentId ? { ...i, status: newStatus } : i));
      if (selectedIncident?.id === incidentId) {
        setSelectedIncident(prev => prev ? { ...prev, status: newStatus } : null);
      }
    } catch (error) {
      console.error("Failed to update status", error);
    }
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

  if (!user) {
    return (
      <div className="flex flex-col items-center justify-center h-screen p-4">
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="max-w-md w-full text-center"
        >
          <img src="/favicon.png" alt="Vigilinex Logo" className="w-24 h-24 mx-auto mb-6 object-contain drop-shadow-lg" />
          <h1 className="text-4xl font-bold mb-2 tracking-tighter uppercase italic">Vigilinex</h1>
          <p className="text-sm opacity-60 mb-8 font-mono uppercase tracking-widest">Incident Intelligence Platform</p>
          <button onClick={handleLogin} className="btn-primary w-full py-4 flex items-center justify-center gap-2">
            <UserIcon size={18} /> Enter Dashboard
          </button>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-black p-4 flex items-center justify-between sticky top-0 bg-[#E4E3E0] z-10">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 cursor-pointer hover:opacity-80 transition-opacity" onClick={() => {setView('dashboard'); loadIncidents();}}>
            <img src="/favicon.png" alt="Vigilinex Logo" className="w-8 h-8 object-contain drop-shadow-sm" />
            <h1 className="text-xl font-bold tracking-tighter uppercase italic m-0">Vigilinex</h1>
          </div>
          <div className="hidden md:flex items-center gap-2 text-[10px] font-mono uppercase opacity-50">
            <Activity size={12} className="text-green-600 animate-pulse" /> Stream Connected
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
              {loading && <div className="p-4 text-center font-mono text-xs uppercase opacity-50"><Activity className="inline animate-spin"/> Syncing Database...</div>}
              
              <div className="flex flex-col md:flex-row gap-4 items-end justify-between">
                <div className="flex flex-wrap gap-4 items-center w-full md:w-auto">
                  <div className="relative flex-1 md:w-64">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 opacity-30" size={14} />
                    <input 
                      type="text" 
                      placeholder="SEARCH INCIDENTS..." 
                      className="input-field text-xs font-mono uppercase"
                      style={{ paddingLeft: '2.5rem' }}
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
                      <div className="data-value opacity-30 text-[10px]">{String(incident.id).padStart(4, '0')}</div>
                      <div className="font-medium truncate pr-4 text-sm">{incident.title}</div>
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
                    <div className="flex items-center gap-1"><UserIcon size={12} /> {selectedIncident.reporterName || selectedIncident.reporterUid}</div>
                    <div className="flex items-center gap-1"><Clock size={12} /> {selectedIncident.createdAt.toDate().toLocaleString()}</div>
                    <div className="flex items-center gap-1"><Info size={12} /> {selectedIncident.category}</div>
                  </div>
                  <div className="text-lg leading-relaxed font-serif opacity-80 whitespace-pre-wrap">
                    {selectedIncident.description}
                  </div>
                </div>

                {(selectedIncident as any).rcaSummary && (
                  <div className="border border-black p-6 bg-white shadow-[4px_4px_0px_rgba(0,0,0,1)]">
                    <div className="flex items-center gap-2 mb-4">
                      <Shield className="text-blue-600" size={24} />
                      <h2 className="col-header text-blue-900 m-0">AI Root Cause Analysis</h2>
                    </div>
                    <div className="text-sm leading-relaxed font-serif italic markdown-body">
                      <Markdown>{(selectedIncident as any).rcaSummary}</Markdown>
                    </div>
                    {(selectedIncident as any).probableCause && (
                      <div className="mt-4 pt-4 border-t border-black/10 flex items-start gap-2">
                        <AlertTriangle className="text-amber-500 shrink-0 mt-1" size={16} />
                        <div>
                          <span className="text-[10px] font-mono uppercase font-bold block mb-1 text-black/50">Probable Cause</span>
                          <span className="text-sm font-medium">{(selectedIncident as any).probableCause}</span>
                        </div>
                      </div>
                    )}
                  </div>
                )}

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
                    <div className="flex items-center gap-2 text-xs font-mono opacity-50">
                      <MapPin size={14} /> 
                      Assumed remote system
                    </div>
                  </div>
                </div>

                <div className="border border-black p-6 bg-black text-white space-y-4">
                  <h3 className="text-[10px] font-mono uppercase opacity-50">Intelligence Note</h3>
                  <p className="text-xs font-serif italic leading-relaxed opacity-80">
                    This incident is actively monitored by the Vigilinex Inference Engine. Communications are analyzed for threat vectors.
                  </p>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* Footer */}
      <footer className="border-t border-black p-4 text-[10px] font-mono uppercase opacity-30 flex justify-between">
        <div>Vigilinex Incident Intelligence</div>
        <div>{new Date().getFullYear()} © Sentinel Systems</div>
      </footer>
    </div>
  );
}
