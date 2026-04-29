"""
FastAPI server for SaaS Co-Pilot
"""
import os
import json
import re
import sqlite3
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from groq import Groq

from database import init_db

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="SaaS Co-Pilot API", version="1.0.0")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database path
DB_PATH = "saas_data.db"


def get_db_connection():
    """Get a database connection using raw sqlite3"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def execute_sql_query(query: str) -> Dict[str, Any]:
    """Execute SQL query and return results using raw sqlite3"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(query)
        rows = [dict(r) for r in cur.fetchall()]
        columns = list(rows[0].keys()) if rows else []
        return {"columns": columns, "rows": rows}
    except Exception as e:
        return {"error": str(e), "rows": [], "columns": []}
    finally:
        if conn:
            conn.close()


# Initialize database on startup
@app.on_event("startup")
def startup_event():
    init_db()


# Pydantic models
class QuestionRequest(BaseModel):
    question: str


class ChartData(BaseModel):
    labels: List[str]
    values: List[float]
    additional_data: Optional[List[Dict[str, Any]]] = None


class AIResponse(BaseModel):
    sql: str
    chart_type: str  # bar, line, pie
    insight: str
    data: Dict[str, Any]


# Initialize Groq client
groq_client = None
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)


def determine_chart_type(data: List[Dict], columns: List[str]) -> str:
    """Determine appropriate chart type based on data"""
    if not data:
        return "bar"
    
    # Check if we have time series data
    time_keywords = ['month', 'year', 'date', 'time', 'quarter', 'week']
    first_col_lower = columns[0].lower() if columns else ""
    
    if any(keyword in first_col_lower for keyword in time_keywords):
        return "line"
    
    # If we have 2-3 categories, pie chart works well
    if len(data) <= 5 and len(columns) == 2:
        return "pie"
    
    return "bar"


def ask_groq(prompt: str, system_prompt: str = None) -> str:
    """Send prompt to Groq API"""
    if not groq_client:
        return "Groq API key not configured. Please set GROQ_API_KEY in .env file."
    
    try:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.1,
            max_tokens=2000
        )
        
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error calling Groq API: {str(e)}"


@app.get("/")
def read_root():
    return {"message": "SaaS Co-Pilot API is running", "version": "1.0.0"}


@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.post("/ask", response_model=AIResponse)
def ask_question(request: QuestionRequest):
    """
    Convert natural language question to SQL, execute it, and return insights
    """
    # Get database schema info for the AI
    schema_info = """
    Database Schema:
    - clients: id, name, plan (Starter/Pro/Enterprise), country, joined_date
    - revenue: id, client_id, amount, month (YYYY-MM format), status (paid/unpaid)
    - support_tickets: id, client_id, issue, priority (High/Medium/Low), status (open/in_progress/resolved/closed), created_at
    - usage_logs: id, client_id, feature, usage_count, month (YYYY-MM format)
    
    Example questions you can answer:
    - "What is the total revenue by plan type?"
    - "Show me monthly revenue trends"
    - "Which clients have the most support tickets?"
    - "What are the most used features?"
    - "How many enterprise clients do we have by country?"
    - "What is the average revenue per client?"
    """
    
    system_prompt = """You are a SQL expert that converts natural language questions into SQLite queries.
    Return your response in the following JSON format:
    {
        "sql": "SELECT ...",
        "insight": "Brief insight about what this query shows (2-3 sentences)"
    }
    
    Rules:
    1. Only use the tables and columns mentioned in the schema
    2. Use proper SQL syntax for SQLite
    3. Always include meaningful column aliases
    4. For date comparisons, use the month column which is in YYYY-MM format
    5. Keep queries simple and efficient
    6. Do not include any markdown formatting in the JSON"""
    
    prompt = f"""Based on the database schema below, convert this question into a SQL query:
    
    Question: {request.question}
    
    {schema_info}
    
    Return only valid JSON with 'sql' and 'insight' keys."""
    
    response = ask_groq(prompt, system_prompt)
    
    # Parse the AI response
    try:
        # Try to extract JSON from the response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            ai_result = json.loads(json_match.group())
        else:
            ai_result = json.loads(response)
    except (json.JSONDecodeError, AttributeError):
        ai_result = {
            "sql": "SELECT name, plan FROM clients LIMIT 10",
            "insight": "Could not parse the question. Here's a sample query."
        }
    
    sql_query = ai_result.get("sql", "SELECT 1")
    insight = ai_result.get("insight", "Query executed")
    
    # Clean up SQL (remove markdown code blocks if present)
    sql_query = re.sub(r'```sql\s*|\s*```', '', sql_query).strip()
    
    # Execute the query using raw sqlite3
    rows = []
    columns = []
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(sql_query)
        rows = [dict(r) for r in cur.fetchall()]
        if rows:
            columns = list(rows[0].keys())
    except Exception as e:
        insight = f"Error executing query: {str(e)}. Please rephrase your question."
    finally:
        if conn:
            conn.close()
    
    # Determine chart type
    chart_type = determine_chart_type(rows, columns)
    
    # Prepare data for frontend
    if rows:
        # Get labels and values for charting
        if len(columns) >= 2:
            labels = [str(row[columns[0]]) for row in rows]
            # Try to find numeric column for values
            values = []
            for col in columns[1:]:
                try:
                    values = [float(row[col]) for row in rows]
                    break
                except (ValueError, TypeError):
                    continue
            if not values:
                values = [1] * len(rows)  # Default to 1 if no numeric column
        else:
            labels = [str(list(row.values())[0]) for row in rows]
            values = [1] * len(rows)
        
        chart_data = {
            "labels": labels,
            "values": values,
            "raw_data": rows
        }
    else:
        chart_data = {
            "labels": [],
            "values": [],
            "raw_data": []
        }
    
    return AIResponse(
        sql=sql_query,
        chart_type=chart_type,
        insight=insight,
        data=chart_data
    )


@app.get("/digest")
def get_weekly_digest():
    """
    Generate a weekly business health summary using AI
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Gather statistics using raw SQL
    cur.execute("SELECT COUNT(*) FROM clients")
    total_clients = cur.fetchone()[0]
    
    cur.execute("SELECT plan, COUNT(*) FROM clients GROUP BY plan")
    clients_by_plan = cur.fetchall()
    
    cur.execute("SELECT SUM(amount) FROM revenue")
    total_revenue = cur.fetchone()[0] or 0
    
    cur.execute("SELECT month, SUM(amount) FROM revenue GROUP BY month ORDER BY month")
    monthly_revenue = cur.fetchall()
    
    cur.execute("SELECT SUM(amount) FROM revenue WHERE status = 'unpaid'")
    unpaid_revenue = cur.fetchone()[0] or 0
    
    cur.execute("SELECT COUNT(*) FROM support_tickets")
    total_tickets = cur.fetchone()[0]
    
    cur.execute("SELECT priority, COUNT(*) FROM support_tickets GROUP BY priority")
    tickets_by_priority = cur.fetchall()
    
    cur.execute("SELECT COUNT(*) FROM support_tickets WHERE status IN ('open', 'in_progress')")
    open_tickets = cur.fetchone()[0]
    
    cur.execute("SELECT feature, SUM(usage_count) FROM usage_logs GROUP BY feature ORDER BY SUM(usage_count) DESC LIMIT 5")
    top_features = cur.fetchall()
    
    conn.close()
    
    # Format stats for AI
    stats_text = f"""
    Business Statistics:
    - Total Clients: {total_clients}
    - Clients by Plan: {', '.join([f'{row[0]}: {row[1]}' for row in clients_by_plan])}
    - Total Revenue: ${total_revenue:,.2f}
    - Monthly Revenue Trend: {', '.join([f'{row[0]}: ${row[1]:,.2f}' for row in monthly_revenue])}
    - Unpaid Revenue: ${unpaid_revenue:,.2f}
    - Total Support Tickets: {total_tickets}
    - Tickets by Priority: {', '.join([f'{row[0]}: {row[1]}' for row in tickets_by_priority])}
    - Open/In-Progress Tickets: {open_tickets}
    - Top 5 Features by Usage: {', '.join([f'{row[0]}: {row[1]:,} uses' for row in top_features])}
    """
    
    system_prompt = """You are a business analyst AI assistant. Generate a comprehensive weekly business health digest."""
    
    prompt = f"""Based on the following business statistics, generate a comprehensive weekly business health digest.
    Include:
    1. Executive Summary (2-3 sentences)
    2. Revenue Analysis
    3. Customer Insights
    4. Support Overview
    5. Key Recommendations
    
    {stats_text}
    
    Format the response in a professional, easy-to-read manner with clear sections."""
    
    digest = ask_groq(prompt, system_prompt)
    
    return {
        "digest": digest,
        "generated_at": datetime.now().isoformat(),
        "stats": {
            "total_clients": total_clients,
            "total_revenue": round(total_revenue, 2),
            "unpaid_revenue": round(unpaid_revenue, 2),
            "total_tickets": total_tickets,
            "open_tickets": open_tickets
        }
    }


@app.get("/anomalies")
def detect_anomalies():
    """
    Detect business anomalies and risks from current data
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    anomalies = []
    
    # Check for high unpaid revenue
    cur.execute("SELECT SUM(amount) FROM revenue")
    total_revenue = cur.fetchone()[0] or 0
    
    cur.execute("SELECT SUM(amount) FROM revenue WHERE status = 'unpaid'")
    unpaid_revenue = cur.fetchone()[0] or 0
    unpaid_percentage = (unpaid_revenue / total_revenue * 100) if total_revenue > 0 else 0
    
    if unpaid_percentage > 10:
        anomalies.append({
            "type": "warning",
            "title": "High Unpaid Revenue",
            "description": f"Unpaid revenue is ${unpaid_revenue:,.2f} ({unpaid_percentage:.1f}% of total). This is above the 10% threshold.",
            "metric": f"${unpaid_revenue:,.2f} unpaid"
        })
    
    # Check for clients with many open support tickets
    cur.execute("""
        SELECT c.name, COUNT(st.id) as ticket_count
        FROM clients c
        JOIN support_tickets st ON c.id = st.client_id
        WHERE st.status IN ('open', 'in_progress')
        GROUP BY c.id
        HAVING COUNT(st.id) >= 3
    """)
    clients_with_tickets = cur.fetchall()
    
    for row in clients_with_tickets:
        client_name = row[0]
        count = row[1]
        anomalies.append({
            "type": "critical" if count >= 5 else "warning",
            "title": f"Multiple Open Tickets: {client_name}",
            "description": f"This client has {count} open/in-progress support tickets. Consider proactive outreach.",
            "metric": f"{count} open tickets"
        })
    
    # Check for revenue decline
    cur.execute("""
        SELECT month, SUM(amount) as total
        FROM revenue
        GROUP BY month
        ORDER BY month
    """)
    monthly_revenue = cur.fetchall()
    
    if len(monthly_revenue) >= 2:
        last_month = monthly_revenue[-1][1]
        prev_month = monthly_revenue[-2][1]
        if prev_month > 0:
            change = ((last_month - prev_month) / prev_month) * 100
            if change < -15:
                anomalies.append({
                    "type": "critical",
                    "title": "Revenue Decline Detected",
                    "description": f"Revenue decreased by {abs(change):.1f}% from {monthly_revenue[-2][0]} to {monthly_revenue[-1][0]}. Investigate potential causes.",
                    "metric": f"{change:.1f}% change"
                })
            elif change < -5:
                anomalies.append({
                    "type": "warning",
                    "title": "Slight Revenue Decline",
                    "description": f"Revenue decreased by {abs(change):.1f}% from {monthly_revenue[-2][0]} to {monthly_revenue[-1][0]}. Monitor closely.",
                    "metric": f"{change:.1f}% change"
                })
    
    # Check for high-priority unresolved tickets
    cur.execute("""
        SELECT COUNT(*) FROM support_tickets
        WHERE priority = 'High' AND status IN ('open', 'in_progress')
    """)
    high_priority_open = cur.fetchone()[0]
    
    if high_priority_open > 0:
        anomalies.append({
            "type": "critical",
            "title": "High Priority Tickets Pending",
            "description": f"There are {high_priority_open} high-priority support tickets that are still open or in progress.",
            "metric": f"{high_priority_open} tickets"
        })
    
    # Check for clients with declining usage
    current_month = "2024-06"
    prev_month_val = "2024-05"
    
    cur.execute("""
        SELECT c.name, SUM(ul.usage_count) as current_usage
        FROM clients c
        JOIN usage_logs ul ON c.id = ul.client_id
        WHERE ul.month = ?
        GROUP BY c.id
    """, (current_month,))
    declining_clients = cur.fetchall()
    
    cur.execute("""
        SELECT c.name, SUM(ul.usage_count) as prev_usage
        FROM clients c
        JOIN usage_logs ul ON c.id = ul.client_id
        WHERE ul.month = ?
        GROUP BY c.id
    """, (prev_month_val,))
    prev_usage = cur.fetchall()
    
    prev_usage_dict = {row[0]: row[1] for row in prev_usage}
    
    for row in declining_clients:
        client_name = row[0]
        current = row[1]
        if client_name in prev_usage_dict:
            prev = prev_usage_dict[client_name]
            if prev > 0:
                decline = ((current - prev) / prev) * 100
                if decline < -30:
                    anomalies.append({
                        "type": "warning",
                        "title": f"Usage Decline: {client_name}",
                        "description": f"Client usage dropped by {abs(decline):.1f}% from {prev_month_val} to {current_month}. Risk of churn.",
                        "metric": f"{decline:.1f}% decline"
                    })
    
    # Ensure we have at least 3 anomalies for demo purposes
    if len(anomalies) < 3:
        # Add some informational items
        cur.execute("SELECT COUNT(*) FROM clients WHERE plan = 'Starter'")
        starter_clients = cur.fetchone()[0]
        if starter_clients > 0:
            anomalies.append({
                "type": "info",
                "title": "Upgrade Opportunities",
                "description": f"There are {starter_clients} Starter plan clients that could be targeted for upselling to Pro.",
                "metric": f"{starter_clients} clients"
            })
    
    conn.close()
    
    # Use AI to analyze and prioritize anomalies
    if anomalies and groq_client:
        anomaly_text = "\n".join([f"- {a['title']}: {a['description']}" for a in anomalies])
        
        prompt = f"""Analyze these business anomalies and provide a brief summary with prioritized recommendations:

{anomaly_text}

Return a short summary (3-4 sentences) focusing on the most critical issues and recommended actions."""
        
        ai_analysis = ask_groq(prompt)
    else:
        ai_analysis = "No AI analysis available. Review the anomalies manually."
    
    return {
        "anomalies": anomalies,
        "ai_analysis": ai_analysis,
        "detected_at": datetime.now().isoformat(),
        "total_count": len(anomalies),
        "critical_count": len([a for a in anomalies if a["type"] == "critical"])
    }


@app.get("/clients")
def get_clients():
    """Get all clients"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    cur.execute("SELECT id, name, plan, country, joined_date FROM clients")
    clients = cur.fetchall()
    conn.close()
    
    return [
        {
            "id": c["id"],
            "name": c["name"],
            "plan": c["plan"],
            "country": c["country"],
            "joined_date": c["joined_date"]
        }
        for c in clients
    ]


@app.get("/revenue/summary")
def get_revenue_summary():
    """Get revenue summary by plan"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    cur.execute("""
        SELECT c.plan, SUM(r.amount) as total_revenue, COUNT(c.id) as client_count
        FROM clients c
        JOIN revenue r ON c.id = r.client_id
        GROUP BY c.plan
    """)
    result = cur.fetchall()
    conn.close()
    
    return [
        {
            "plan": row["plan"],
            "total_revenue": round(row["total_revenue"], 2),
            "client_count": row["client_count"]
        }
        for row in result
    ]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)