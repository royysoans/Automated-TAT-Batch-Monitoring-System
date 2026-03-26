# Laboratory TAT & Batch Monitoring System

A clinical-grade, automated monitoring system for Laboratory Turnaround Time (TAT) and Batch processing. Fully integrated with Neon PostgreSQL and Vercel Serverless.

## 🚀 System Architecture

- **Dashboard (Next.js):** Premium, high-density UI for real-time sample oversight.
- **Backend (FastAPI):** Serverless API handling EDOS logic, ETA calculation, and breach detection.
- **Database (Neon PostgreSQL):** Cloud-hosted relational storage for 100% persistence.
- **Monitoring (GitHub Actions):** Periodic (5-min) background scanning for TAT breaches.

## 🛠️ Deployment Configuration

### 1. Environment Variables (Vercel)
You must set the following in your Vercel Project Settings:
- `DATABASE_URL`: Your Neon PostgreSQL connection string.

### 2. GitHub Secrets (Monitoring)
To enable the 5-minute background breach check, add this to your GitHub Repository Settings > Secrets > Actions:
- `VERCEL_URL`: The full URL of your deployed Vercel app (e.g., `https://your-app.vercel.app`).

## 📡 API Flow
1. **Sample Accession:** External systems POST to `/api/webhook/sample`.
2. **Logic Engine:** System parses EDOS schedules, assigns the correct batch, and calculates the exact ETA.
3. **Breach Monitor:** GitHub Actions pings `/api/alerts/check-breaches` every 5 minutes to identify overdue samples.
4. **Dashboard:** Live updates with animated alerts and vertical lifecycle timelines.

---
*Built with Antigravity for Clinical Excellence.*
