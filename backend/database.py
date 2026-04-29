"""
Database setup and seed data for SaaS Co-Pilot
"""
import os
import random
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# Database setup
DATABASE_URL = "sqlite:///./saas_data.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Database Models
class Client(Base):
    __tablename__ = "clients"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    plan = Column(String)  # Starter, Pro, Enterprise
    country = Column(String)
    joined_date = Column(Date)
    
    revenue = relationship("Revenue", back_populates="client")
    support_tickets = relationship("SupportTicket", back_populates="client")
    usage_logs = relationship("UsageLog", back_populates="client")


class Revenue(Base):
    __tablename__ = "revenue"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    amount = Column(Float)
    month = Column(String)
    status = Column(String)  # paid, unpaid
    
    client = relationship("Client", back_populates="revenue")


class SupportTicket(Base):
    __tablename__ = "support_tickets"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    issue = Column(String)
    priority = Column(String)  # High, Medium, Low
    status = Column(String)  # open, in_progress, resolved, closed
    created_at = Column(DateTime)
    
    client = relationship("Client", back_populates="support_tickets")


class UsageLog(Base):
    __tablename__ = "usage_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    feature = Column(String)
    usage_count = Column(Integer)
    month = Column(String)
    
    client = relationship("Client", back_populates="usage_logs")


def get_db():
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def seed_database():
    """Seed the database with fake SaaS data"""
    # Check if data already exists
    db = SessionLocal()
    if db.query(Client).first():
        db.close()
        return
    
    try:
        # Client data - 15 clients with realistic names
        clients_data = [
            {"name": "TechCorp Solutions", "plan": "Enterprise", "country": "United States", "joined_date": "2023-01-15"},
            {"name": "StartupHub Inc", "plan": "Starter", "country": "Canada", "joined_date": "2024-02-20"},
            {"name": "DataFlow Systems", "plan": "Pro", "country": "United Kingdom", "joined_date": "2023-06-10"},
            {"name": "CloudNine Technologies", "plan": "Enterprise", "country": "Germany", "joined_date": "2022-11-05"},
            {"name": "InnovateLabs", "plan": "Pro", "country": "Australia", "joined_date": "2023-09-22"},
            {"name": "Digital Dynamics", "plan": "Starter", "country": "India", "joined_date": "2024-01-08"},
            {"name": "NextGen Analytics", "plan": "Enterprise", "country": "Singapore", "joined_date": "2023-03-17"},
            {"name": "ByteBridge Co", "plan": "Pro", "country": "Netherlands", "joined_date": "2023-07-30"},
            {"name": "SmartScale Ltd", "plan": "Starter", "country": "France", "joined_date": "2024-03-12"},
            {"name": "QuantumLeap AI", "plan": "Enterprise", "country": "Japan", "joined_date": "2022-08-25"},
            {"name": "PixelPerfect Design", "plan": "Pro", "country": "Brazil", "joined_date": "2023-11-14"},
            {"name": "CodeCraft Studios", "plan": "Starter", "country": "Mexico", "joined_date": "2024-02-01"},
            {"name": "Velocity Ventures", "plan": "Pro", "country": "Spain", "joined_date": "2023-05-08"},
            {"name": "FusionWorks Global", "plan": "Enterprise", "country": "Sweden", "joined_date": "2023-02-28"},
            {"name": "EcoMetrics Inc", "plan": "Starter", "country": "Ireland", "joined_date": "2024-04-05"},
        ]
        
        clients = []
        for c in clients_data:
            client = Client(
                name=c["name"],
                plan=c["plan"],
                country=c["country"],
                joined_date=datetime.strptime(c["joined_date"], "%Y-%m-%d").date()
            )
            db.add(client)
            clients.append(client)
        db.commit()
        
        # Revenue data - monthly revenue for each client
        months = ["2024-01", "2024-02", "2024-03", "2024-04", "2024-05", "2024-06"]
        plan_pricing = {"Starter": (99, 149), "Pro": (299, 499), "Enterprise": (999, 1999)}
        
        for client in clients:
            price_range = plan_pricing[client.plan]
            for month in months:
                # Some months might not have revenue for newer clients
                client_join_month = client.joined_date.strftime("%Y-%m")
                if month < client_join_month:
                    continue
                
                amount = random.uniform(price_range[0], price_range[1])
                # Enterprise clients sometimes have custom pricing
                if client.plan == "Enterprise":
                    amount = random.uniform(price_range[0], price_range[1] * 1.5)
                
                revenue = Revenue(
                    client_id=client.id,
                    amount=round(amount, 2),
                    month=month,
                    status=random.choices(["paid", "unpaid"], weights=[85, 15])[0]
                )
                db.add(revenue)
        db.commit()
        
        # Support tickets
        issues = [
            "Login authentication failure",
            "API rate limit exceeded",
            "Data export not working",
            "Billing discrepancy",
            "Feature request: Dark mode",
            "Slow dashboard loading",
            "Integration with Slack broken",
            "User permissions not saving",
            "Mobile app sync issues",
            "Webhook notifications delayed",
            "Report generation timeout",
            "SSO configuration help needed",
            "Data visualization bug",
            "Account upgrade issues",
            "Email notifications not received"
        ]
        
        priorities = ["High", "Medium", "Low"]
        statuses = ["open", "in_progress", "resolved", "closed"]
        
        for client in clients:
            # Each client has 1-5 tickets
            num_tickets = random.randint(1, 5)
            for _ in range(num_tickets):
                days_ago = random.randint(1, 90)
                ticket = SupportTicket(
                    client_id=client.id,
                    issue=random.choice(issues),
                    priority=random.choices(priorities, weights=[20, 45, 35])[0],
                    status=random.choices(statuses, weights=[15, 20, 35, 30])[0],
                    created_at=datetime.now() - timedelta(days=days_ago, hours=random.randint(0, 23))
                )
                db.add(ticket)
        db.commit()
        
        # Usage logs
        features = [
            "API Calls", "Dashboard Views", "Report Generation", 
            "Data Exports", "User Management", "Integrations",
            "Automated Workflows", "Custom Dashboards", "Alerts Created",
            "Team Collaborations"
        ]
        
        for client in clients:
            for month in months:
                client_join_month = client.joined_date.strftime("%Y-%m")
                if month < client_join_month:
                    continue
                
                # Select 3-6 random features per client per month
                selected_features = random.sample(features, random.randint(3, 6))
                for feature in selected_features:
                    # Usage varies by plan
                    if client.plan == "Starter":
                        usage = random.randint(10, 500)
                    elif client.plan == "Pro":
                        usage = random.randint(100, 5000)
                    else:  # Enterprise
                        usage = random.randint(500, 50000)
                    
                    usage_log = UsageLog(
                        client_id=client.id,
                        feature=feature,
                        usage_count=usage,
                        month=month
                    )
                    db.add(usage_log)
        db.commit()
        
        print(f"Database seeded successfully!")
        print(f"  - {len(clients)} clients")
        print(f"  - {db.query(Revenue).count()} revenue records")
        print(f"  - {db.query(SupportTicket).count()} support tickets")
        print(f"  - {db.query(UsageLog).count()} usage logs")
        
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise
    finally:
        db.close()


# Create tables
def init_db():
    """Initialize the database"""
    Base.metadata.create_all(bind=engine)
    seed_database()


if __name__ == "__main__":
    init_db()