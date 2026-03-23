import { GoogleGenAI, Type } from "@google/genai";

const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

export async function analyzeIncident(title: string, description: string) {
  try {
    const response = await ai.models.generateContent({
      model: "gemini-3-flash-preview",
      contents: `Analyze the following incident report and suggest a severity level (low, medium, high, critical) and a category (e.g., Security, Infrastructure, Software, Hardware, Other).

Title: ${title}
Description: ${description}`,
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            suggestedSeverity: {
              type: Type.STRING,
              enum: ["low", "medium", "high", "critical"],
              description: "The suggested severity level based on the description."
            },
            suggestedCategory: {
              type: Type.STRING,
              description: "A concise category for the incident."
            },
            summary: {
              type: Type.STRING,
              description: "A one-sentence summary of the incident."
            }
          },
          required: ["suggestedSeverity", "suggestedCategory", "summary"]
        }
      }
    });

    const text = response.text;
    if (text) {
      return JSON.parse(text);
    }
  } catch (error) {
    console.error("Gemini analysis error:", error);
  }
  return null;
}

export async function generateIncidentSummary(incidents: any[]) {
  try {
    const incidentData = incidents.map(i => ({
      title: i.title,
      severity: i.severity,
      status: i.status,
      createdAt: i.createdAt.toDate().toISOString()
    }));

    const response = await ai.models.generateContent({
      model: "gemini-3-flash-preview",
      contents: `Provide a high-level executive summary of the current incident landscape based on these reports. Highlight critical issues and trends.

Incidents: ${JSON.stringify(incidentData)}`,
    });

    return response.text;
  } catch (error) {
    console.error("Gemini summary error:", error);
  }
  return "Unable to generate summary at this time.";
}
