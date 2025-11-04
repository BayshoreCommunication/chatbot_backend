# 🤖 FAQ Intelligence API Documentation

## Overview

The FAQ Intelligence API provides **real-time analysis** of your chatbot's knowledge base and suggests improvements. **NO DATA IS STORED** - analysis runs only when requested.

---

## 🎯 What It Checks

### 1. **Organization Profile** ✅

- Organization Name
- Website URL
- Company/Organization Type

### 2. **FAQ Availability** ✅

- Number of FAQs in knowledge base
- Quality assessment (none/minimal/good/excellent)

### 3. **Website Content** 🌐

- Scrapes your website for training content
- Analyzes quality and relevance
- Identifies topics covered

### 4. **Training Documents** 📄

- Analyzes uploaded PDFs
- Extracts key information
- Suggests missing content

### 5. **Conversation Patterns** 💬

- Analyzes customer questions
- Identifies common topics
- Finds unanswered questions

---

## 📡 API Endpoints

### 1. Full Analysis (AI-Powered)

**Endpoint:** `GET /api/faq-intelligence/analyze`

**Headers:**

```http
X-API-Key: org_sk_your_api_key_here
```

**Response:**

```json
{
  "status": "success",
  "timestamp": "2025-11-04T10:30:00",
  "readiness_score": 75,
  "alerts": [
    {
      "type": "warning",
      "category": "profile",
      "message": "⚠️ Company type is missing",
      "action": "Specify your company/organization type for better AI suggestions"
    },
    {
      "type": "critical",
      "category": "faqs",
      "message": "❌ No FAQs found in your knowledge base",
      "action": "Add at least 5-10 FAQs to help the AI provide better responses"
    }
  ],
  "suggestions": [
    {
      "type": "missing_faq",
      "priority": "high",
      "category": "Service",
      "question": "What types of personal injury cases do you handle?",
      "suggested_answer": "We handle car accidents, slip and fall cases...",
      "reasoning": "This is a fundamental question for law firms",
      "source": "ai_analysis"
    },
    {
      "type": "conversation_pattern",
      "priority": "high",
      "question": "What are your consultation fees?",
      "reasoning": "Multiple customers asked this in recent conversations",
      "source": "customer_conversations"
    }
  ],
  "analysis": {
    "profile": {
      "complete": false,
      "missing_critical_fields": ["company_organization_type"],
      "completion_percentage": 66.67
    },
    "faqs": {
      "has_faqs": true,
      "count": 8,
      "quality": "good"
    },
    "website": {
      "success": true,
      "word_count": 1234,
      "content_quality": "good",
      "found_topics": ["Services", "About Us", "Contact"]
    },
    "conversations": {
      "analyzed_count": 50,
      "common_questions": [
        "What are your fees?",
        "Do you offer free consultation?"
      ],
      "missing_topics": ["Pricing", "Consultation Process"]
    }
  }
}
```

**Alert Types:**

- `critical` - Must fix for basic functionality
- `warning` - Should fix for better performance
- `info` - Optional improvements
- `error` - Technical issues

---

### 2. Quick Check (No AI)

**Endpoint:** `GET /api/faq-intelligence/quick-check`

**Headers:**

```http
X-API-Key: org_sk_your_api_key_here
```

**Response:**

```json
{
  "status": "success",
  "readiness_score": 60,
  "alerts": [
    {
      "type": "warning",
      "message": "⚠️ Website URL is missing",
      "action": "Add your website URL to enable content analysis"
    }
  ],
  "stats": {
    "profile_complete": false,
    "missing_fields": ["website", "company_organization_type"],
    "faq_count": 5,
    "document_count": 2,
    "conversation_count": 45
  },
  "recommendation": "Run full analysis for detailed suggestions"
}
```

**Use Cases:**

- Dashboard widgets
- Quick status checks
- Frequent monitoring (no AI costs)

---

### 3. Get Company Types

**Endpoint:** `GET /api/faq-intelligence/company-types`

**Response:**

```json
{
  "status": "success",
  "company_types": [
    "Law Firm",
    "Personal Injury Law Firm",
    "Medical Practice",
    "Restaurant",
    "E-commerce Store",
    "SaaS Company",
    ...
  ]
}
```

---

## 🚀 Usage Examples

### JavaScript/TypeScript

```typescript
// Full Analysis
const analyzeKnowledgeBase = async () => {
  const response = await fetch("/api/faq-intelligence/analyze", {
    headers: {
      "X-API-Key": "org_sk_your_key",
    },
  });

  const data = await response.json();

  // Show alerts
  data.alerts.forEach((alert) => {
    console.log(`[${alert.type}] ${alert.message}`);
    console.log(`Action: ${alert.action}`);
  });

  // Show suggestions
  data.suggestions.forEach((suggestion) => {
    console.log(`[${suggestion.priority}] ${suggestion.question}`);
    console.log(`Answer: ${suggestion.suggested_answer}`);
  });

  console.log(`Readiness Score: ${data.readiness_score}/100`);
};

// Quick Check
const quickCheck = async () => {
  const response = await fetch("/api/faq-intelligence/quick-check", {
    headers: {
      "X-API-Key": "org_sk_your_key",
    },
  });

  const data = await response.json();
  console.log(`Score: ${data.readiness_score}/100`);
  console.log(`FAQs: ${data.stats.faq_count}`);
};
```

### Python

```python
import requests

# Full Analysis
def analyze_knowledge_base(api_key):
    response = requests.get(
        'http://localhost:8000/api/faq-intelligence/analyze',
        headers={'X-API-Key': api_key}
    )
    data = response.json()

    print(f"Readiness Score: {data['readiness_score']}/100")

    for alert in data['alerts']:
        print(f"[{alert['type']}] {alert['message']}")

    for suggestion in data['suggestions']:
        print(f"Q: {suggestion['question']}")
        print(f"A: {suggestion['suggested_answer']}\n")

    return data

# Run analysis
result = analyze_knowledge_base('org_sk_your_key')
```

### cURL

```bash
# Full Analysis
curl -X GET "http://localhost:8000/api/faq-intelligence/analyze" \
  -H "X-API-Key: org_sk_your_key"

# Quick Check
curl -X GET "http://localhost:8000/api/faq-intelligence/quick-check" \
  -H "X-API-Key: org_sk_your_key"

# Get Company Types
curl -X GET "http://localhost:8000/api/faq-intelligence/company-types"
```

---

## 📊 Readiness Score Calculation

The readiness score (0-100) is calculated based on:

| Component                | Points | Criteria                                   |
| ------------------------ | ------ | ------------------------------------------ |
| **Profile Completeness** | 30     | All required fields filled                 |
| **FAQ Availability**     | 40     | 10+ FAQs = 40pts, 5-9 = 30pts, 1-4 = 20pts |
| **Website Content**      | 15     | Accessible with 500+ words                 |
| **Training Documents**   | 10     | At least 1 PDF uploaded                    |
| **Conversation Data**    | 5      | 10+ conversations logged                   |

**Score Interpretation:**

- `90-100` - Excellent! Your AI is well-trained
- `70-89` - Good, but could use more content
- `50-69` - Needs improvement
- `0-49` - Critical issues, immediate action needed

---

## ⚙️ Setup

### 1. Add OpenAI API Key

Add to `.env` file:

```bash
OPENAI_API_KEY=sk-your-openai-key-here
```

### 2. Install Dependencies

Already installed via:

```bash
pip install langchain langchain-openai chromadb tiktoken pypdf beautifulsoup4
```

### 3. Restart Backend

```bash
cd chatbot_backend
uvicorn main:app --reload
```

---

## 🎨 Frontend Integration Example

### React Admin Dashboard

```tsx
import React, { useState, useEffect } from "react";

const FAQIntelligence = () => {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);

  const runAnalysis = async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/faq-intelligence/analyze", {
        headers: {
          "X-API-Key": localStorage.getItem("apiKey"),
        },
      });
      const data = await response.json();
      setAnalysis(data);
    } catch (error) {
      console.error("Analysis failed:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="faq-intelligence">
      <h2>FAQ Intelligence Dashboard</h2>

      <button onClick={runAnalysis} disabled={loading}>
        {loading ? "Analyzing..." : "Run Analysis"}
      </button>

      {analysis && (
        <>
          {/* Readiness Score */}
          <div className="score-card">
            <h3>Readiness Score</h3>
            <div className="score">{analysis.readiness_score}/100</div>
          </div>

          {/* Alerts */}
          <div className="alerts">
            <h3>Alerts ({analysis.alerts.length})</h3>
            {analysis.alerts.map((alert, i) => (
              <div key={i} className={`alert alert-${alert.type}`}>
                <p>{alert.message}</p>
                <p className="action">{alert.action}</p>
              </div>
            ))}
          </div>

          {/* Suggestions */}
          <div className="suggestions">
            <h3>Suggested FAQs ({analysis.suggestions.length})</h3>
            {analysis.suggestions.map((suggestion, i) => (
              <div key={i} className="suggestion">
                <span className={`priority priority-${suggestion.priority}`}>
                  {suggestion.priority}
                </span>
                <h4>{suggestion.question}</h4>
                <p>{suggestion.suggested_answer}</p>
                <small>{suggestion.reasoning}</small>
                <button onClick={() => addFAQ(suggestion)}>
                  Add to Knowledge Base
                </button>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
};

export default FAQIntelligence;
```

---

## 🔐 Security Notes

1. **API Key Required** - All endpoints require valid X-API-Key header
2. **No Data Storage** - Analysis is performed in real-time, not stored
3. **Organization Scoped** - Each analysis only accesses data for the authenticated organization
4. **OpenAI API Usage** - Consumes OpenAI credits for AI analysis (not quick-check)

---

## 💡 Best Practices

### When to Run Full Analysis

- ✅ After adding new FAQs
- ✅ After uploading new training documents
- ✅ Weekly/monthly for optimization
- ✅ When readiness score is low

### When to Use Quick Check

- ✅ Dashboard widgets (real-time status)
- ✅ Before important demos/launches
- ✅ Daily monitoring
- ✅ Frequent status updates

### Optimizing Results

1. **Complete Profile** - Fill all organization details
2. **Add Comprehensive FAQs** - Aim for 10-20 quality FAQs
3. **Upload Documents** - Add service guides, policies, procedures
4. **Update Website** - Ensure website has detailed service information
5. **Monitor Conversations** - Review customer questions regularly

---

## 📈 Expected Response Times

| Endpoint                     | Typical Duration | AI Usage |
| ---------------------------- | ---------------- | -------- |
| `/quick-check`               | < 1 second       | No       |
| `/analyze` (no website/docs) | 3-5 seconds      | Yes      |
| `/analyze` (with website)    | 10-15 seconds    | Yes      |
| `/analyze` (full)            | 20-30 seconds    | Yes      |

---

## 🐛 Troubleshooting

### "OpenAI API key not configured"

**Solution:** Add `OPENAI_API_KEY=sk-...` to `.env` file and restart backend

### "Could not fetch website content"

**Causes:**

- Website is behind authentication
- Website blocks web scrapers
- Invalid URL

**Solution:** Ensure website is publicly accessible

### "Failed to parse AI response"

**Cause:** OpenAI returned invalid JSON

**Solution:** Check `raw_response` in result, retry analysis

---

## 🆘 Support

For issues or questions:

1. Check logs: Look for `[FAQ-INTELLIGENCE]` entries
2. Verify OpenAI API key is valid
3. Ensure all dependencies are installed
4. Check organization profile is complete

---

## 📝 Example Workflow

```bash
# 1. Quick check to see current status
GET /api/faq-intelligence/quick-check

# If score < 70...

# 2. Run full analysis
GET /api/faq-intelligence/analyze

# 3. Review alerts and fix critical issues
# - Add missing organization info
# - Add initial FAQs

# 4. Run analysis again
GET /api/faq-intelligence/analyze

# 5. Implement suggested FAQs
# - Add to knowledge base via FAQ API

# 6. Monitor with quick checks
# - Daily/weekly via dashboard widget
```

---

## 🎯 Success Metrics

**Target Goals:**

- ✅ Readiness Score: 80+
- ✅ No Critical Alerts
- ✅ 10+ Quality FAQs
- ✅ Website content analyzed
- ✅ At least 1 training document

**Achievement Benefits:**

- 📈 Better AI response quality
- ⚡ Faster customer query resolution
- 😊 Higher customer satisfaction
- 🎯 Reduced unknown question rate
