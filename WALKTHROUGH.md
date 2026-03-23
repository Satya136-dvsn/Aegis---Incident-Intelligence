# Aegis Incident Intelligence — Feature Walkthrough

Welcome to the walkthrough of Aegis, an AI-powered incident management platform. This document highlights the core features and how they function within the platform.

## 🚀 1. Real-Time Dashboard

The dashboard is the central hub where all incidents are tracked. It uses **Firebase Firestore** for real-time synchronization, meaning every change (new reports, status updates, comments) is instantly visible to all connected users.

- **Dynamic Filtering:** Filter incidents by severity (`Critical`, `High`, `Medium`, `Low`) or status (`Open`, `In Progress`, etc.).
- **Global Search:** Find incidents by searching through titles and descriptions in real-time.

## 📝 2. Incident Reporting

Reporting an incident is a streamlined process with built-in AI assistance.

- **Structured Forms:** Capture essential data (Title, Description, Severity, Category).
- **AI Suggested Severity:** Behind the scenes, the **Gemini 3 Flash** model analyzes the description to suggest the most appropriate severity level, ensuring consistency across reports.

## 🤖 3. AI-Powered Intelligence

Aegis goes beyond simple tracking by providing deep analysis:

- **Executive Summary:** Click the "Regenerate Analysis" button to get a high-level overview of the entire incident landscape. Gemini identifies trends, recurring issues, and critical risks.
- **Root Cause Analysis (RCA):** For any incident, the platform can trigger a deep-dive analysis (via the `/api/v1/rca` endpoint) to identify probable causes and suggest fixes based on recent system logs and metrics.

## 🌐 4. Metric Simulator (SRE View)

The backend includes a fully functional **SRE Metric Simulator** that broadcasts live system data via WebSockets:

- **Live Metrics:** Monitor CPU, Memory, API Latency, and Error Rates.
- **Anomaly Injection:** Watch how the system identifies spikes (e.g., CPU hitting 95%) and triggers critical alerts in the UI.

## 🔐 5. Security & RBAC

The platform is secured by a robust **Role-Based Access Control (RBAC)** system:

- **Google Auth:** Integrated authentication via Firebase.
- **Three-Tier Roles:** `Admin` (Full control), `Responder` (Triage & Work), `Reporter` (Submit & View).
- **Server-Side Security:** 136 lines of Firestore Security Rules ensure that even if the frontend is bypassed, the database remains secure.

---

*Aegis Incident Intelligence // Built with React, Firebase, and Gemini AI*
