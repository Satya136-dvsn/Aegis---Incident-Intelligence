import express from "express";
import { createServer as createViteServer } from "vite";
import path from "path";
import { WebSocketServer, WebSocket } from "ws";
import http from "http";
import { GoogleGenAI } from "@google/genai";
import dotenv from "dotenv";

dotenv.config();

const PORT = 3000;
const GEMINI_API_KEY = process.env.GEMINI_API_KEY;

async function startServer() {
  const app = express();
  const server = http.createServer(app);
  const wss = new WebSocketServer({ server });

  app.use(express.json());

  // AI RCA Engine Endpoint
  app.post("/api/v1/rca", async (req, res) => {
    const { anomaly, metrics, logs } = req.body;
    
    if (!GEMINI_API_KEY) {
      return res.status(500).json({ error: "Gemini API key not configured" });
    }

    try {
      const ai = new GoogleGenAI({ apiKey: GEMINI_API_KEY });
      const model = ai.models.generateContent({
        model: "gemini-3-flash-preview",
        contents: `Analyze the following system anomaly and provide a root cause analysis in JSON format.
        
        Anomaly: ${JSON.stringify(anomaly)}
        Recent Metrics: ${JSON.stringify(metrics)}
        Recent Logs: ${JSON.stringify(logs)}
        
        Return JSON with:
        - probable_cause (string)
        - contributing_factors (array of strings)
        - suggested_fixes (array of strings)`,
        config: {
          responseMimeType: "application/json",
        }
      });

      const response = await model;
      res.json(JSON.parse(response.text));
    } catch (error) {
      console.error("AI RCA Error:", error);
      res.status(500).json({ error: "Failed to generate RCA" });
    }
  });

  // Health check
  app.get("/api/v1/health", (req, res) => {
    res.json({ status: "ok", timestamp: new Date().toISOString() });
  });

  // WebSocket for real-time metrics
  wss.on("connection", (ws) => {
    console.log("Client connected to metrics stream");
    ws.on("close", () => console.log("Client disconnected"));
  });

  // Broadcast function for simulator
  const broadcast = (data: any) => {
    wss.clients.forEach((client) => {
      if (client.readyState === WebSocket.OPEN) {
        client.send(JSON.stringify(data));
      }
    });
  };

  // Simulator Logic
  const SERVICES = ["auth-service", "payment-gateway", "order-processor"];
  const METRIC_TYPES = ["cpu_usage", "memory_usage", "api_response_time_ms", "error_rate_percent"];

  setInterval(() => {
    const service = SERVICES[Math.floor(Math.random() * SERVICES.length)];
    const metricType = METRIC_TYPES[Math.floor(Math.random() * METRIC_TYPES.length)];
    
    let value = 0;
    let isAnomaly = false;

    // Normal ranges
    if (metricType === "cpu_usage") value = 20 + Math.random() * 40;
    if (metricType === "memory_usage") value = 40 + Math.random() * 30;
    if (metricType === "api_response_time_ms") value = 100 + Math.random() * 200;
    if (metricType === "error_rate_percent") value = Math.random() * 2;

    // Inject anomaly (5% chance)
    if (Math.random() < 0.05) {
      isAnomaly = true;
      if (metricType === "cpu_usage") value = 90 + Math.random() * 10;
      if (metricType === "memory_usage") value = 95 + Math.random() * 5;
      if (metricType === "api_response_time_ms") value = 2500 + Math.random() * 1000;
      if (metricType === "error_rate_percent") value = 15 + Math.random() * 20;
    }

    const metric = {
      service_name: service,
      metric_type: metricType,
      value: parseFloat(value.toFixed(2)),
      timestamp: new Date().toISOString(),
      is_anomaly: isAnomaly,
    };

    broadcast({ type: "METRIC", data: metric });

    if (isAnomaly) {
      const log = {
        service_name: service,
        level: "CRITICAL",
        message: `High ${metricType} detected: ${value.toFixed(2)}`,
        timestamp: new Date().toISOString(),
      };
      broadcast({ type: "LOG", data: log });
    }
  }, 2000);

  // Vite middleware for development
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  server.listen(PORT, "0.0.0.0", () => {
    console.log(`Server running on http://localhost:${PORT}`);
  });
}

startServer();
