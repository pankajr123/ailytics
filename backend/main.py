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


@app.get("/stats")
def get_stats():
    """
    Get quick stats from uploaded_data table:
    - total_revenue: Sum of revenue/amount/monthly_revenue column
    - active_clients: Count of unique clients (from client/name column)
    - growth_rate: N/A (not calculable without time series data)
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
        table_exists = cur.fetchone() is not None

        if not table_exists:
            return {
                "total_revenue": 0,
                "active_clients": 0,
                "growth_rate": "N/A"
            }

        # Check if table has any rows
        cur.execute("SELECT COUNT(*) FROM uploaded_data")
        row_count = cur.fetchone()[0]

        if row_count == 0:
            return {
                "total_revenue": 0,
                "active_clients": 0,
                "growth_rate": "N/A"
            }

        # Get column names
        cur.execute("PRAGMA table_info(uploaded_data)")
        columns_info = cur.fetchall()
        columns = [col[1].lower() for col in columns_info]

        # Try to find revenue column
        revenue_keywords = ['revenue', 'amount', 'monthly_revenue', 'sales', 'total', 'price']
        revenue_column = None
        for col in columns:
            for keyword in revenue_keywords:
                if keyword in col:
                    revenue_column = col
                    break
            if revenue_column:
                break

        # Try to find client column
        client_keywords = ['client', 'name', 'customer', 'company', 'account']
        client_column = None
        for col in columns:
            for keyword in client_keywords:
                if keyword in col:
                    client_column = col
                    break
            if client_column:
                break

        # Calculate total revenue
        total_revenue = 0
        if revenue_column:
            cur.execute(f'SELECT SUM("{revenue_column}") FROM uploaded_data')
            result = cur.fetchone()
            if result and result[0] is not None:
                total_revenue = round(float(result[0]), 2)

        # Calculate active clients count
        active_clients = 0
        if client_column:
            cur.execute(f'SELECT COUNT(DISTINCT "{client_column}") FROM uploaded_data')
            result = cur.fetchone()
            if result and result[0] is not None:
                active_clients = int(result[0])
        else:
            # If no client column, count total rows as active clients
            active_clients = row_count

        return {
            "total_revenue": total_revenue,
            "active_clients": active_clients,
            "growth_rate": "N/A"
        }

    except Exception as e:
        return {
            "total_revenue": 0,
            "active_clients": 0,
            "growth_rate": "N/A"
        }
    finally:
        if conn:
            conn.close()


@app.post("/ask", response_model=AIResponse)
def ask_question(request: QuestionRequest):
    """
    Convert natural language question to SQL, execute it, and return insights
    Uses uploaded_data table only.
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
        if not cur.fetchone():
            # Return error response if table doesn't exist
            return AIResponse(
                sql="SELECT 1",
                chart_type="bar",
                insight="No CSV data uploaded. Please upload a CSV file first using the upload feature.",
                data={"labels": [], "values": [], "raw_data": []}
            )
        
        # Get columns from uploaded_data: PRAGMA table_info(uploaded_data)
        cur.execute("PRAGMA table_info(uploaded_data)")
        columns_info = cur.fetchall()
        column_names = [col[1] for col in columns_info]
        
        # Get 3 sample rows: SELECT * FROM uploaded_data LIMIT 3
        cur.execute("SELECT * FROM uploaded_data LIMIT 3")
        sample_rows = cur.fetchall()
        sample_data = [dict(row) for row in sample_rows]
    finally:
        if conn:
            conn.close()
    
    # Build schema_info dynamically from these columns
    schema_info = f"""
    Database Schema (table: uploaded_data):
    Columns: {', '.join(column_names)}
    
    Sample data:
    {chr(10).join([str(row) for row in sample_data])}
    
    Example questions you can answer:
    - "Show me top 5 rows"
    - "What are the column names?"
    - "Show me summary statistics"
    - "What is the count by {column_names[0] if column_names else 'column'}?"
    """
    
    system_prompt = """You are a SQL expert that converts natural language questions into SQLite queries.
    Return your response in the following JSON format:
    {
        "sql": "SELECT ...",
        "insight": "Direct answer to the user question based on query results in 2-3 sentences"
    }
    
    Rules:
    1. Only use the 'uploaded_data' table
    2. Use proper SQL syntax for SQLite
    3. Always include meaningful column aliases
    4. Keep queries simple and efficient
    5. Do not include any markdown formatting in the JSON
    6. Use the exact column names from the schema"""
    
    prompt = f"""Based on the database schema below, convert this question into a SQL query:
    
    Question: {request.question}
    
    {schema_info}
    
    Return only valid JSON with 'sql' and 'insight' keys. The insight must directly answer the question asked, like 'The total revenue is $X' or 'Client Y has the highest tickets'. Start with the actual answer."""
    
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
            "sql": "SELECT * FROM uploaded_data LIMIT 10",
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
    Generate a weekly business health summary using AI from uploaded_data table only.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Check if uploaded_data exists and has rows
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='uploaded_data'")
        table_exists = cur.fetchone() is not None
        
        if not table_exists:
            return {
                "digest": "No data uploaded yet. Please upload a CSV file to generate digest.",
                "generated_at": datetime.now().isoformat(),
                "stats": {
                    "total_clients": 0,
                    "total_revenue": 0,
                    "unpaid_revenue": 0,
                    "total_tickets": 0,
                    "open_tickets": 0
                }
            }
        
        # Check if table has any rows
        cur.execute("SELECT COUNT(*) FROM uploaded_data")
        row_count = cur.fetchone()[0]
        
        if row_count == 0:
            return {
                "digest": "No data uploaded yet. Please upload a CSV file to generate digest.",
                "generated_at": datetime.now().isoformat(),
                "stats": {
                    "total_clients": 0,
                    "total_revenue": 0,
                    "unpaid_revenue": 0,
                    "total_tickets": 0,
                    "open_tickets": 0
                }
            }
        
        # Get all column names from uploaded_data
        cur.execute("PRAGMA table_info(uploaded_data)")
        columns_info = cur.fetchall()
        column_names = [col[1] for col in columns_info]
        
        # Get all rows: SELECT * FROM uploaded_data
        cur.execute("SELECT * FROM uploaded_data")
        all_rows = cur.fetchall()
        all_data = [dict(row) for row in all_rows]
        
        # Calculate stats from uploaded_data dynamically
        # Try to find revenue column
        revenue_keywords = ['revenue', 'amount', 'monthly_revenue', 'sales', 'total', 'price']
        revenue_column = None
        for col in column_names:
            for keyword in revenue_keywords:
                if keyword in col.lower():
                    revenue_column = col
                    break
            if revenue_column:
                break
        
        # Try to find client column
        client_keywords = ['client', 'name', 'customer', 'company', 'account']
        client_column = None
        for col in column_names:
            for keyword in client_keywords:
                if keyword in col.lower():
                    client_column = col
                    break
            if client_column:
                break
        
        # Calculate total revenue
        total_revenue = 0
        if revenue_column:
            cur.execute(f'SELECT SUM("{revenue_column}") FROM uploaded_data')
            result = cur.fetchone()
            if result and result[0] is not None:
                total_revenue = round(float(result[0]), 2)
        
        # Calculate total clients (unique values in client column or total rows)
        total_clients = 0
        if client_column:
            cur.execute(f'SELECT COUNT(DISTINCT "{client_column}") FROM uploaded_data')
            result = cur.fetchone()
            if result and result[0] is not None:
                total_clients = int(result[0])
        else:
            total_clients = row_count
        
        # For unpaid revenue and tickets, we don't have specific columns
        # so we'll let AI analyze the data to find these insights
        unpaid_revenue = 0
        total_tickets = 0
        open_tickets = 0
        
    finally:
        if conn:
            conn.close()
    
    # Format data for AI - send full data
    data_str = "\n".join([str(row) for row in all_data[:100]])  # Limit to 100 rows for API
    columns_str = ", ".join(column_names)
    
    stats_text = f"""
    Uploaded Data Statistics:
    - Total Rows: {row_count}
    - Columns: {columns_str}
    - Total Clients/Entries: {total_clients}
    - Total Revenue (if applicable): ${total_revenue:,.2f}
    
    Sample Data (first 5 rows):
    {chr(10).join([str(row) for row in all_data[:5]])}
    """
    
    system_prompt = """You are a business analyst AI assistant. Generate a comprehensive weekly business health digest from the uploaded data."""
    
    prompt = f"""Based on the following uploaded business data, generate a comprehensive weekly business health digest.
    Include:
    1. Executive Summary (2-3 sentences)
    2. Key Metrics Analysis
    3. Data Insights
    4. Trends and Patterns
    5. Key Recommendations
    
    {stats_text}
    
    Full Data:
    {data_str}
    
    Format the response in a professional, easy-to-read manner with clear sections."""
    
    digest = ask_groq(prompt, system_prompt)
    
    return {
        "digest": digest,
        "generated_at": datetime.now().isoformat(),
        "stats": {
            "total_clients": total_clients,
            "total_revenue": total_revenue,
            "unpaid_revenue": unpaid_revenue,
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
            cur.execute("DELETE FROM uploaded_data")
            
            # Store in SQLite
            df.to_sql('uploaded_data', conn, if_exists='replace', index=False)
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
        "insight": "Direct answer to the user question based on query results in 2-3 sentences"
    }
    
    Rules:
    1. Only use the 'uploaded_data' table
    2. Use proper SQL syntax for SQLite
    3. Always include meaningful column aliases
    4. Keep queries simple and efficient
    5. Do not include any markdown formatting in the JSON
    6. Use the exact column names from the schema
    7. Always include FROM uploaded_data in every query"""
    
    prompt = f"""Based on the uploaded CSV data schema below, convert this question into a SQL query:
    
    Question: {request.question}
    
    {schema_info}
    
    Return only valid JSON with 'sql' and 'insight' keys. The insight must directly answer the question asked, like 'The total revenue is $X' or 'Client Y has the highest tickets'. Start with the actual answer."""
    
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
    
    # Fix: Add FROM uploaded_data if missing
    if 'FROM' not in sql_query.upper():
        sql_query = sql_query + ' FROM uploaded_data'
    
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
            
            if row_count == 0:
                return {"uploaded": False}
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
        
        cur.execute("DELETE FROM uploaded_data")
        conn.commit()
    finally:
        if conn:
            conn.close()
    
    return {"success": True, "message": "Data cleared"}


@app.delete("/clear-data")
def clear_data():
    """Clear all rows from uploaded_data table"""
    import time
    last_error = None
    for attempt in range(5):
        conn = None
        try:
            conn = sqlite3.connect(DB_PATH, timeout=60, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=30000")
            cur = conn.cursor()
            cur.execute("DELETE FROM uploaded_data")
            conn.commit()
            return {"success": True}
        except sqlite3.OperationalError as e:
            last_error = str(e)
            time.sleep(1)
        finally:
            if conn:
                conn.close()
    return {"success": False, "error": last_error}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
