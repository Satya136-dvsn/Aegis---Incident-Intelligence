import { Timestamp } from 'firebase/firestore';

export type Severity = 'low' | 'medium' | 'high' | 'critical';
export type Status = 'open' | 'in-progress' | 'resolved' | 'closed';
export type UserRole = 'admin' | 'responder' | 'reporter';

export interface UserProfile {
  uid: string;
  email: string;
  displayName: string | null;
  role: UserRole;
  createdAt: Timestamp;
}

export interface Incident {
  id: string;
  title: string;
  description: string;
  severity: Severity;
  status: Status;
  category: string;
  reporterUid: string;
  reporterName: string;
  createdAt: Timestamp;
  updatedAt: Timestamp;
  location?: {
    latitude: number;
    longitude: number;
  };
}

export interface Comment {
  id: string;
  incidentId: string;
  text: string;
  authorUid: string;
  authorName: string;
  createdAt: Timestamp;
}
