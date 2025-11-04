# 📊 FAQ Intelligence - Analysis History & Progress Tracking

## Overview

The FAQ Intelligence system now **stores the last 5 analysis reports** for each organization, enabling:

- ✅ Historical tracking of readiness scores
- ✅ Progress visualization over time
- ✅ Trend analysis (improving/declining/stable)
- ✅ Comparison metrics
- ✅ Better user experience with saved reports

---

## 🎯 Features

### 1. **Automatic Report Storage**

Every time you run an analysis (full or quick), the system:

- Saves the complete report to database
- Keeps only the **last 5 reports** per organization
- Automatically deletes older reports

### 2. **Progress Tracking**

- View score improvements over time
- See trends (improving/declining/stable)
- Track FAQ count, document count changes
- Get personalized recommendations

### 3. **Historical Comparison**

- Compare current vs. previous scores
- Identify what changed between analyses
- Monitor alert count trends

---

## 📡 New API Endpoints

### 1. Get Analysis History

**Endpoint:** `GET /api/faq-intelligence/history`

**Headers:**

```http
X-API-Key: org_sk_your_api_key
```

**Response:**

```json
{
  "status": "success",
  "reports": [
    {
      "_id": "507f1f77bcf86cd799439011",
      "organization_id": "org_123",
      "analysis_type": "full",
      "readiness_score": 75,
      "timestamp": "2025-11-04T10:30:00",
      "alerts": [...],
      "suggestions": [...],
      "stats": {
        "faq_count": 8,
        "document_count": 2,
        "conversation_count": 45,
        "profile_complete": true,
        "missing_fields": []
      }
    },
    {
      "analysis_type": "quick",
      "readiness_score": 65,
      "timestamp": "2025-11-03T14:20:00",
      "stats": {
        "faq_count": 5,
        "document_count": 1,
        "conversation_count": 30
      }
    }
  ],
  "progress": {
    "latest_score": 75,
    "score_trend": "improving",
    "total_analyses": 12,
    "last_analysis_date": "2025-11-04T10:30:00"
  }
}
```

**Score Trends:**

- `improving` - Score increased by 5+ points
- `declining` - Score decreased by 5+ points
- `stable` - Score changed by less than 5 points
- `no_data` - No previous reports to compare

---

### 2. Get Progress Tracking

**Endpoint:** `GET /api/faq-intelligence/progress`

**Headers:**

```http
X-API-Key: org_sk_your_api_key
```

**Response:**

```json
{
  "status": "success",
  "timeline": [
    {
      "date": "2025-11-01T09:00:00",
      "score": 45,
      "type": "quick",
      "faq_count": 3,
      "alert_count": 5
    },
    {
      "date": "2025-11-02T14:30:00",
      "score": 60,
      "type": "full",
      "faq_count": 7,
      "alert_count": 3
    },
    {
      "date": "2025-11-04T10:30:00",
      "score": 75,
      "type": "full",
      "faq_count": 8,
      "alert_count": 1
    }
  ],
  "metrics": {
    "first_score": 45,
    "latest_score": 75,
    "improvement": 30,
    "average_score": 60.0,
    "total_analyses": 3,
    "trend": "improving"
  },
  "recommendations": [
    "Great progress! Your score improved by 30 points.",
    "Add more FAQs and training documents for better AI performance."
  ]
}
```

**Recommendation Messages:**

- Score < 50: "Critical: Complete your organization profile and add FAQs."
- Score 50-69: "Add more FAQs and training documents for better AI performance."
- Score 70-89: "Almost there! Review AI suggestions to reach excellence."
- Score 90+: "Excellent setup! Maintain this quality."

---

### 3. Clear Analysis History

**Endpoint:** `DELETE /api/faq-intelligence/history`

**Headers:**

```http
X-API-Key: org_sk_your_api_key
```

**Response:**

```json
{
  "status": "success",
  "message": "Deleted 5 analysis reports",
  "deleted_count": 5
}
```

---

## 🔄 How It Works

### Automatic Storage Flow

```
1. User runs analysis (full or quick)
   ↓
2. System performs analysis
   ↓
3. Results returned to user
   ↓
4. Report saved to database
   ↓
5. System checks report count
   ↓
6. If > 5 reports, delete oldest ones
   ↓
7. Keep only last 5 reports
```

### Stored Report Structure

```json
{
  "organization_id": "org_123",
  "analysis_type": "full" | "quick",
  "readiness_score": 75,
  "timestamp": "2025-11-04T10:30:00",
  "alerts": [...],
  "suggestions": [...],
  "analysis": {...},
  "stats": {
    "faq_count": 8,
    "document_count": 2,
    "conversation_count": 45,
    "profile_complete": true,
    "missing_fields": []
  }
}
```

---

## 📊 Database Collection

**Collection Name:** `faq_analysis_reports`

**Indexes:**

```javascript
db.faq_analysis_reports.createIndex({ organization_id: 1, timestamp: -1 });
```

**Storage Limit:** 5 reports per organization (automatic cleanup)

---

## 💡 Usage Examples

### Frontend Integration - History View

```typescript
import React, { useState, useEffect } from "react";

const AnalysisHistory = () => {
  const [history, setHistory] = useState(null);

  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    const response = await fetch("/api/faq-intelligence/history", {
      headers: {
        "X-API-Key": localStorage.getItem("apiKey"),
      },
    });
    const data = await response.json();
    setHistory(data);
  };

  return (
    <div className="history-container">
      <h2>Analysis History</h2>

      {/* Progress Summary */}
      <div className="progress-summary">
        <div className="score-card">
          <h3>Current Score</h3>
          <div className="score">{history?.progress.latest_score}/100</div>
          <span className={`trend trend-${history?.progress.score_trend}`}>
            {history?.progress.score_trend}
          </span>
        </div>
        <div className="stats">
          <p>Total Analyses: {history?.progress.total_analyses}</p>
          <p>
            Last Check:{" "}
            {new Date(
              history?.progress.last_analysis_date
            ).toLocaleDateString()}
          </p>
        </div>
      </div>

      {/* Report List */}
      <div className="report-list">
        {history?.reports.map((report, index) => (
          <div key={report._id} className="report-card">
            <div className="report-header">
              <span className="date">
                {new Date(report.timestamp).toLocaleDateString()}
              </span>
              <span className="type">{report.analysis_type}</span>
              <span className="score">{report.readiness_score}/100</span>
            </div>

            <div className="report-stats">
              <span>📋 {report.stats.faq_count} FAQs</span>
              <span>📄 {report.stats.document_count} Docs</span>
              <span>💬 {report.stats.conversation_count} Convos</span>
            </div>

            {report.alerts.length > 0 && (
              <div className="alerts">
                <strong>Alerts: {report.alerts.length}</strong>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
```

### Frontend - Progress Chart

```typescript
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";

const ProgressChart = () => {
  const [progressData, setProgressData] = useState(null);

  useEffect(() => {
    fetchProgress();
  }, []);

  const fetchProgress = async () => {
    const response = await fetch("/api/faq-intelligence/progress", {
      headers: {
        "X-API-Key": localStorage.getItem("apiKey"),
      },
    });
    const data = await response.json();
    setProgressData(data);
  };

  return (
    <div className="progress-chart">
      <h2>Progress Over Time</h2>

      <div className="metrics">
        <div className="metric">
          <span className="label">Improvement</span>
          <span
            className={`value ${
              progressData?.metrics.improvement > 0 ? "positive" : "negative"
            }`}
          >
            {progressData?.metrics.improvement > 0 ? "+" : ""}
            {progressData?.metrics.improvement}
          </span>
        </div>
        <div className="metric">
          <span className="label">Average Score</span>
          <span className="value">{progressData?.metrics.average_score}</span>
        </div>
      </div>

      <LineChart width={600} height={300} data={progressData?.timeline}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" />
        <YAxis domain={[0, 100]} />
        <Tooltip />
        <Line
          type="monotone"
          dataKey="score"
          stroke="#8884d8"
          strokeWidth={2}
        />
      </LineChart>

      <div className="recommendations">
        <h3>Recommendations</h3>
        <ul>
          {progressData?.recommendations.map((rec, i) => (
            <li key={i}>{rec}</li>
          ))}
        </ul>
      </div>
    </div>
  );
};
```

### Python - Fetch History

```python
import requests

def get_analysis_history(api_key):
    response = requests.get(
        'http://localhost:8000/api/faq-intelligence/history',
        headers={'X-API-Key': api_key}
    )
    data = response.json()

    print(f"Latest Score: {data['progress']['latest_score']}/100")
    print(f"Trend: {data['progress']['score_trend']}")

    for report in data['reports']:
        print(f"\n{report['timestamp']}: {report['readiness_score']}/100")
        print(f"  FAQs: {report['stats']['faq_count']}")
        print(f"  Alerts: {len(report['alerts'])}")
```

---

## 🎯 Benefits

### For Users

✅ **Track Progress** - See improvements over time  
✅ **Historical Context** - Understand what changed  
✅ **Motivation** - Visual proof of progress  
✅ **Insights** - Identify patterns and trends

### For Admins

✅ **User Engagement** - Track who's using the feature  
✅ **Performance Metrics** - Monitor score improvements  
✅ **Usage Analytics** - See analysis frequency

---

## 🔐 Privacy & Storage

- ✅ **Organization Scoped** - Each org only sees their own reports
- ✅ **Limited Storage** - Only 5 reports kept (automatic cleanup)
- ✅ **Optional Deletion** - Users can clear history anytime
- ✅ **No External Storage** - All data in your MongoDB

---

## 📈 Metrics Calculation

### Score Trend

```python
if latest_score > previous_score + 5:
    trend = "improving"
elif latest_score < previous_score - 5:
    trend = "declining"
else:
    trend = "stable"
```

### Improvement Score

```python
improvement = latest_score - first_score
```

### Average Score

```python
average = sum(all_scores) / total_reports
```

---

## 🚀 Quick Start

### 1. Run Your First Analysis

```bash
curl -X GET "http://localhost:8000/api/faq-intelligence/quick-check" \
  -H "X-API-Key: org_sk_your_key"
```

### 2. View History

```bash
curl -X GET "http://localhost:8000/api/faq-intelligence/history" \
  -H "X-API-Key: org_sk_your_key"
```

### 3. Track Progress

```bash
curl -X GET "http://localhost:8000/api/faq-intelligence/progress" \
  -H "X-API-Key: org_sk_your_key"
```

---

## 🎨 Dashboard Widget Example

```html
<div class="faq-intelligence-widget">
  <h3>FAQ Readiness</h3>

  <!-- Current Score -->
  <div class="current-score">
    <span class="score-value">75</span>
    <span class="score-max">/100</span>
    <span class="trend improving">↑ Improving</span>
  </div>

  <!-- Mini Chart -->
  <div class="mini-chart">
    <!-- Previous 5 scores as small bars -->
    <div class="bar" style="height: 45%"></div>
    <div class="bar" style="height: 60%"></div>
    <div class="bar" style="height: 65%"></div>
    <div class="bar" style="height" style="height: 70%"></div>
    <div class="bar" style="height: 75%"></div>
  </div>

  <!-- Quick Stats -->
  <div class="quick-stats">
    <span>8 FAQs</span>
    <span>2 Docs</span>
    <span>1 Alert</span>
  </div>

  <button onclick="runAnalysis()">Run New Analysis</button>
</div>
```

---

## 📝 Summary

The FAQ Intelligence system now provides:

✅ **Automatic Storage** - Last 5 reports saved  
✅ **Progress Tracking** - Score trends over time  
✅ **Historical View** - All past analyses  
✅ **Metrics & Insights** - Improvement tracking  
✅ **Recommendations** - Based on trends  
✅ **Clean UI Data** - Ready for charts/widgets

Perfect for building engaging analytics dashboards! 📊
