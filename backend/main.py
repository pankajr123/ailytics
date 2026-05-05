"""
FastAPI server for SaaS Co-Pilot
"""
import os
import json
import re
import sqlite3
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv
from groq import Groq
import pandas as pd
import io
import csv

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
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.row_factory = sqlite3.Row
    return conn


def execute_sql_query(query: str) -> Dict[str, Any]:
    """Execute SQL query and return results using raw sqlite3"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
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
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
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
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
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
    finally:
        if conn:
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
    Detect business anomalies and risks from uploaded CSV data using AI
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Check if uploaded_data table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='uploaded_data'")
        uploaded_table_exists = cur.fetchone() is not None
        
        if not uploaded_table_exists:
            return {"anomalies": [], "total_count": 0}
        
        # Check if table has any rows
        cur.execute("SELECT COUNT(*) FROM uploaded_data")
        row_count = cur.fetchone()[0]
        
        if row_count == 0:
            return {"anomalies": [], "total_count": 0}
        
        # Get columns: PRAGMA table_info(uploaded_data)
        cur.execute("PRAGMA table_info(uploaded_data)")
        columns_info = cur.fetchall()
        columns = [col[1] for col in columns_info]
        
        # Get data: SELECT * FROM uploaded_data LIMIT 10
        cur.execute("SELECT * FROM uploaded_data LIMIT 10")
        sample_rows = cur.fetchall()
        sample_data = [dict(row) for row in sample_rows]
    finally:
        if conn:
            conn.close()
    
    # Call Groq with the specified prompt
    if groq_client:
        cols_str = ", ".join(columns)
        data_str = "\n".join([str(row) for row in sample_data])
        
        prompt = f"""Analyze this business data and return ONLY a JSON array of 3-4 anomalies. No other text. Format: [{{"type":"critical|warning|info","title":"title","description":"desc","metric":"metric"}}]. Columns: {cols_str}. Data: {data_str}"""
        
        try:
            response = ask_groq(prompt)
            
            # Parse and return the JSON array
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                anomalies = json.loads(json_match.group())
            else:
                anomalies = []
        except (json.JSONDecodeError, Exception) as e:
            print(f"Error parsing AI response: {e}")
            anomalies = []
        
        return {"anomalies": anomalies, "total_count": len(anomalies)}
    else:
        return {"anomalies": [], "total_count": 0}


@app.get("/clients")
def get_clients():
    """Get all clients"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        cur.execute("SELECT id, name, plan, country, joined_date FROM clients")
        clients = cur.fetchall()
    finally:
        if conn:
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
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        cur.execute("""
            SELECT c.plan, SUM(r.amount) as total_revenue, COUNT(c.id) as client_count
            FROM clients c
            JOIN revenue r ON c.id = r.client_id
            GROUP BY c.plan
        """)
        result = cur.fetchall()
    finally:
        if conn:
            conn.close()
    
    return [
        {
            "plan": row["plan"],
            "total_revenue": round(row["total_revenue"], 2),
            "client_count": row["client_count"]
        }
        for row in result
    ]


class CSVUploadResponse(BaseModel):
    columns: List[str]
    preview: List[Dict[str, Any]]
    row_count: int
    message: str


@app.post("/upload-csv", response_model=CSVUploadResponse)
async def upload_csv(file: UploadFile = File(...)):
    """
    Upload a CSV file, parse it, and store in uploaded_data table
    """
    # Validate file extension
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    try:
        # Read and parse CSV
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
        
        # Clean column names (remove special characters, spaces)
        df.columns = [col.strip().replace(' ', '_').replace('-', '_') for col in df.columns]
        
        # Drop existing uploaded_data table and recreate
        conn = None
        try:
            conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=10000")
            cur = conn.cursor()
            cur.execute("DROP TABLE IF EXISTS uploaded_data")
            
            # Store in SQLite
            df.to_sql('uploaded_data', conn, if_exists='fail', index=False)
            conn.commit()
            
            # Get preview (first 5 rows)
            preview_df = df.head(5)
            preview = preview_df.to_dict(orient='records')
            
            # Convert any non-serializable types
            for row in preview:
                for key, value in row.items():
                    if pd.isna(value):
                        row[key] = None
                    elif isinstance(value, (pd.Timestamp, datetime)):
                        row[key] = str(value)
        finally:
            if conn:
                conn.close()
        
        return CSVUploadResponse(
            columns=list(df.columns),
            preview=preview,
            row_count=len(df),
            message=f"Successfully uploaded {len(df)} rows with {len(df.columns)} columns"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing CSV: {str(e)}")


@app.post("/ask-csv", response_model=AIResponse)
def ask_csv_question(request: QuestionRequest):
    """
    Convert natural language question to SQL query on uploaded CSV data
    """
    # Check if uploaded_data table exists
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        cur = conn.cursor()
        
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='uploaded_data'")
        if not cur.fetchone():
            raise HTTPException(status_code=400, detail="No CSV data uploaded. Please upload a CSV file first.")
        
        # Get schema info from uploaded_data
        cur.execute("PRAGMA table_info(uploaded_data)")
        columns_info = cur.fetchall()
        columns = [(col[1], col[2]) for col in columns_info]  # (name, type)
        
        # Get sample data for context
        cur.execute("SELECT * FROM uploaded_data LIMIT 3")
        sample_rows = cur.fetchall()
        column_names = [desc[0] for desc in cur.description]
    finally:
        if conn:
            conn.close()
    
    # Build schema info for AI
    schema_info = f"""
    Uploaded CSV Data Schema (table: uploaded_data):
    Columns: {', '.join([f'{col[0]} ({col[1]})' for col in columns])}
    
    Sample data:
    {chr(10).join([str(dict(zip(column_names, row))) for row in sample_rows])}
    
    Example questions you can answer:
    - "What is the average of [numeric_column]?"
    - "Show me the count by [category_column]"
    - "What are the top 5 [column] by [numeric_column]?"
    - "Show me the trend of [numeric_column] over [date_column]"
    """
    
    system_prompt = """You are a SQL expert that converts natural language questions into SQLite queries.
    Return your response in the following JSON format:
    {
        "sql": "SELECT ...",
        "insight": "Brief insight about what this query shows (2-3 sentences)"
    }
    
    Rules:
    1. Only use the 'uploaded_data' table
    2. Use proper SQL syntax for SQLite
    3. Always include meaningful column aliases
    4. Keep queries simple and efficient
    5. Do not include any markdown formatting in the JSON
    6. Use the exact column names from the schema"""
    
    prompt = f"""Based on the uploaded CSV data schema below, convert this question into a SQL query:
    
    Question: {request.question}
    
    {schema_info}
    
    Return only valid JSON with 'sql' and 'insight' keys."""
    
    response = ask_groq(prompt, system_prompt)
    
    # Parse the AI response
    try:
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            ai_result = json.loads(json_match.group())
        else:
            ai_result = json.loads(response)
    except (json.JSONDecodeError, AttributeError):
        ai_result = {
            "sql": "SELECT * FROM uploaded_data LIMIT 10",
            "insight": "Could not parse the question. Here's a sample query."
        }
    
    sql_query = ai_result.get("sql", "SELECT 1")
    insight = ai_result.get("insight", "Query executed")
    
    # Clean up SQL (remove markdown code blocks if present)
    sql_query = re.sub(r'```sql\s*|\s*```', '', sql_query).strip()
    
    # Execute the query
    rows = []
    columns = []
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
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
        if len(columns) >= 2:
            labels = [str(row[columns[0]]) for row in rows]
            values = []
            for col in columns[1:]:
                try:
                    values = [float(row[col]) for row in rows]
                    break
                except (ValueError, TypeError):
                    continue
            if not values:
                values = [1] * len(rows)
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


@app.get("/csv-status")
def get_csv_status():
    """Check if CSV data has been uploaded"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        cur = conn.cursor()
        
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='uploaded_data'")
        exists = cur.fetchone() is not None
        
        if exists:
            cur.execute("SELECT COUNT(*) FROM uploaded_data")
            row_count = cur.fetchone()[0]
            
            cur.execute("PRAGMA table_info(uploaded_data)")
            columns = [(col[1], col[2]) for col in cur.fetchall()]
            
            cur.execute("SELECT * FROM uploaded_data LIMIT 5")
            preview_rows = cur.fetchall()
            column_names = [desc[0] for desc in cur.description]
            preview = [dict(zip(column_names, row)) for row in preview_rows]
            
            return {
                "uploaded": True,
                "row_count": row_count,
                "columns": [{"name": col[0], "type": col[1]} for col in columns],
                "preview": preview
            }
        
        return {"uploaded": False}
    finally:
        if conn:
            conn.close()


@app.delete("/clear-csv")
def clear_csv_data():
    """Clear uploaded CSV data by dropping the uploaded_data table"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        cur = conn.cursor()
        
        cur.execute("DROP TABLE IF EXISTS uploaded_data")
        conn.commit()
    finally:
        if conn:
            conn.close()
    
    return {"success": True, "message": "Data cleared"}


@app.delete("/clear-data")
def clear_data():
    """Clear all rows from uploaded_data table"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        cur = conn.cursor()
        
        cur.execute("DELETE FROM uploaded_data")
        conn.commit()
    finally:
        if conn:
            conn.close()
    
    return {"success": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
