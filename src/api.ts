import { Incident, Comment, Status } from './types';

const BASE_URL = 'http://localhost:8000/api/v1';

export async function fetchIncidents(): Promise<Incident[]> {
  const res = await fetch(`${BASE_URL}/incidents`);
  if (!res.ok) throw new Error('Failed to fetch incidents');
  const json = await res.json();
  
  // Map backend JSON to frontend Incident type 
  // (Handling timestamp conversion from ISO string to Firebase-like object for compatibility)
  return json.data.map((item: any) => ({
    ...item,
    createdAt: { toDate: () => new Date(item.createdAt) },
    updatedAt: { toDate: () => new Date(item.updatedAt) }
  }));
}

export async function fetchComments(incidentId: string): Promise<Comment[]> {
  const res = await fetch(`${BASE_URL}/incidents/${incidentId}/comments`);
  if (!res.ok) throw new Error('Failed to fetch comments');
  const json = await res.json();
  
  return json.data.map((item: any) => ({
    ...item,
    createdAt: { toDate: () => new Date(item.createdAt) }
  }));
}

export async function addComment(incidentId: string, text: string, authorName: string): Promise<Comment> {
  const res = await fetch(`${BASE_URL}/incidents/${incidentId}/comments`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, authorName })
  });
  if (!res.ok) throw new Error('Failed to add comment');
  const json = await res.json();
  
  return {
    ...json.data,
    createdAt: { toDate: () => new Date(json.data.createdAt) }
  };
}

export async function updateIncidentStatus(incidentId: string, status: Status): Promise<void> {
  // In a real app, we'd have a PATCH endpoint for incidents.
  // We'll mock it for now on the frontend since we didn't build it in phase 6 backend yet.
  console.log(`Mock: Updated incident ${incidentId} to ${status}`);
}

export function connectWebSocket(
  onMetric: (data: any) => void,
  onIncident: (data: any) => void
): () => void {
  const ws = new WebSocket('ws://localhost:8000/api/v1/stream/ws');
  
  ws.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data);
      if (payload.type === 'new_metric') {
        onMetric(payload.data);
      } else if (payload.type === 'new_incident') {
        onIncident(payload.data);
      }
    } catch (e) {
      console.error('WebSocket parse error', e);
    }
  };

  ws.onerror = (error) => {
    console.error('WebSocket Error: ', error);
  };

  ws.onopen = () => {
    console.log('Connected to Aegis Intelligence Stream');
  };

  return () => {
    ws.close();
  };
}
