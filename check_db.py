"""
Database health check utility.
Verifies database connection and shows statistics.
"""
from db import get_session, Session, Set, Feedback, Exercise, DATABASE_URL

def check_database():
    """Check database connection and show statistics."""
    print(f"\n🔍 Database Health Check")
    print(f"{'=' * 50}")
    print(f"Database URL: {DATABASE_URL.split('@')[0] + '@***' if '@' in DATABASE_URL else DATABASE_URL}")
    
    if DATABASE_URL.startswith('postgresql'):
        print("✅ Using PostgreSQL (data will persist)")
    else:
        print("⚠️  Using SQLite (local development only)")
    
    try:
        with get_session() as db:
            # Count records
            sessions_count = db.query(Session).count()
            sets_count = db.query(Set).count()
            feedback_count = db.query(Feedback).count()
            exercises_count = db.query(Exercise).count()
            
            print(f"\n📊 Database Statistics:")
            print(f"  Sessions: {sessions_count}")
            print(f"  Logged Sets: {sets_count}")
            print(f"  Feedback Entries: {feedback_count}")
            print(f"  Exercises: {exercises_count}")
            
            # Show recent sessions
            if sessions_count > 0:
                print(f"\n📅 Recent Sessions:")
                recent = db.query(Session).order_by(Session.date.desc()).limit(5).all()
                for sess in recent:
                    status = "✅ Completed" if sess.completed else "⏳ In Progress"
                    print(f"  Session {sess.session_number}: {sess.date} - {status}")
            
            print(f"\n✅ Database is healthy and accessible!")
            return True
            
    except Exception as e:
        print(f"\n❌ Database error: {e}")
        return False

if __name__ == "__main__":
    check_database()
