# SaaS Co-Pilot - AI Data Co-Pilot Dashboard

A modern, AI-powered business intelligence dashboard that allows you to ask natural language questions about your SaaS business data and get instant insights with auto-generated charts.

![SaaS Co-Pilot](https://img.shields.io/badge/version-1.0.0-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## ✨ Features

- **🤖 AI-Powered Chat Interface**: Ask business questions in plain English and get SQL-generated insights
- **📊 Auto-Generated Charts**: Bar, line, and pie charts automatically selected based on data
- **🚨 Anomaly Detection**: AI automatically detects business risks and anomalies
- **📝 Weekly Business Digest**: Comprehensive AI-generated business health summaries
- **🎨 Modern Dark UI**: Professional glassmorphism design with Tailwind CSS
- **⚡ Real-time Insights**: Fast responses powered by Groq's Llama3 70B model

## 🏗️ Project Structure

```
saas-copilot/
├── backend/
│   ├── database.py      # SQLite setup & seed data
│   ├── main.py          # FastAPI routes & AI integration
│   ├── requirements.txt # Python dependencies
│   └── .env.example     # Environment variables template
├── frontend/
│   ├── src/
│   │   ├── App.jsx      # Main dashboard component
│   │   ├── main.jsx     # React entry point
│   │   └── index.css    # Tailwind CSS & custom styles
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── postcss.config.js
└── README.md
```

## 🚀 Getting Started

### Prerequisites

- **Python 3.9+**
- **Node.js 18+**
- **Groq API Key** (Get one free at [console.groq.com](https://console.groq.com))

### Backend Setup

1. **Navigate to the backend directory:**
   ```bash
   cd backend
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   
   # On macOS/Linux
   source venv/bin/activate
   
   # On Windows
   venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add your Groq API key:
   ```
   GROQ_API_KEY=gsk_your_actual_api_key_here
   ```

5. **Run the backend server:**
   ```bash
   python main.py
   ```
   
   The API will be available at `http://localhost:8000`

### Frontend Setup

1. **Open a new terminal and navigate to the frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Start the development server:**
   ```bash
   npm run dev
   ```
   
   The app will be available at `http://localhost:3000`

## 📋 Sample Questions to Try

Once the app is running, try these questions in the chat:

- "What is the total revenue by plan type?"
- "Show me monthly revenue trends"
- "Which clients have the most support tickets?"
- "What are the most used features?"
- "How many enterprise clients do we have?"
- "What is the average revenue per client?"
- "Show me revenue by country"
- "Which features are most popular with Enterprise clients?"

## 🗄️ Database Schema

The application uses SQLite with the following tables:

### Clients
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| name | STRING | Client company name |
| plan | STRING | Starter/Pro/Enterprise |
| country | STRING | Client's country |
| joined_date | DATE | When they joined |

### Revenue
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| client_id | INTEGER | Foreign key to clients |
| amount | FLOAT | Revenue amount |
| month | STRING | YYYY-MM format |
| status | STRING | paid/unpaid |

### Support Tickets
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| client_id | INTEGER | Foreign key to clients |
| issue | STRING | Issue description |
| priority | STRING | High/Medium/Low |
| status | STRING | open/in_progress/resolved/closed |
| created_at | DATETIME | When ticket was created |

### Usage Logs
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| client_id | INTEGER | Foreign key to clients |
| feature | STRING | Feature name |
| usage_count | INTEGER | Usage count |
| month | STRING | YYYY-MM format |

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API health check |
| GET | `/health` | Detailed health status |
| POST | `/ask` | Ask a business question |
| GET | `/digest` | Generate weekly business digest |
| GET | `/anomalies` | Get detected anomalies |
| GET | `/clients` | List all clients |
| GET | `/revenue/summary` | Revenue summary by plan |

## 🛠️ Technology Stack

### Backend
- **FastAPI** - Modern Python web framework
- **SQLAlchemy** - SQL toolkit and ORM
- **SQLite** - Lightweight database
- **Groq** - Ultra-fast AI inference (Llama3 70B)
- **Python-dotenv** - Environment variable management

### Frontend
- **React 18** - UI library
- **Vite** - Fast build tool
- **Tailwind CSS** - Utility-first CSS framework
- **Recharts** - Charting library
- **Lucide React** - Beautiful icons

## 🔧 Troubleshooting

### Backend Issues

**Database not initializing:**
```bash
# Delete the existing database and restart
rm backend/saas_data.db
python backend/main.py
```

**Groq API errors:**
- Ensure your API key is correct in `.env`
- Check your internet connection
- Verify you have API credits available at [Groq Console](https://console.groq.com)

### Frontend Issues

**API connection errors:**
- Ensure the backend is running on port 8000
- Check browser console for CORS errors
- Verify `API_BASE_URL` in `App.jsx` matches your backend URL

**Build errors:**
```bash
# Clear node modules and reinstall
rm -rf node_modules package-lock.json
npm install
```

## 📝 License

This project is licensed under the MIT License.

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 🙏 Acknowledgments

- [Groq](https://groq.com) for providing ultra-fast AI inference
- [FastAPI](https://fastapi.tiangolo.com) for the amazing Python framework
- [Recharts](https://recharts.org) for beautiful charts
- [Tailwind CSS](https://tailwindcss.com) for the utility-first CSS framework

---

**Built with ❤️ for data-driven SaaS businesses**