import sqlite3
from datetime import datetime
from plan import EXERCISE_DEFAULT_SETS, EXERCISE_DEFAULT_REPS, DEFAULT_TARGET_SETS, DEFAULT_TARGET_REPS

def init_database():
    """Initialize the database with tables and sample data."""
    conn = sqlite3.connect('workout.db')
    c = conn.cursor()
    
    # Drop existing tables
    c.execute('DROP TABLE IF EXISTS workout_logs')
    c.execute('DROP TABLE IF EXISTS exercises')
    c.execute('DROP TABLE IF EXISTS workouts')
    
    # Create workouts table
    c.execute('''
        CREATE TABLE workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create exercises table
    c.execute('''
        CREATE TABLE exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workout_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            target_sets INTEGER DEFAULT 3,
            target_reps INTEGER DEFAULT 10,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (workout_id) REFERENCES workouts(id)
        )
    ''')
    
    # Create workout_logs table
    c.execute('''
        CREATE TABLE workout_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exercise_id INTEGER NOT NULL,
            sets_completed INTEGER NOT NULL,
            reps_completed INTEGER NOT NULL,
            weight REAL,
            notes TEXT,
            logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (exercise_id) REFERENCES exercises(id)
        )
    ''')
    
    # Insert sample workout
    c.execute("INSERT INTO workouts (name, description) VALUES (?, ?)", 
              ("Push Day", "Chest, shoulders, and triceps"))
    workout_id = c.lastrowid
    
    # Insert sample exercises with imported constants
    c.execute("INSERT INTO exercises (workout_id, name, target_sets, target_reps) VALUES (?, ?, ?, ?)",
              (workout_id, "Bench Press", DEFAULT_TARGET_SETS, DEFAULT_TARGET_REPS))
    exercise_id = c.lastrowid
    
    # Insert sample workout log
    c.execute("INSERT INTO workout_logs (exercise_id, sets_completed, reps_completed, weight) VALUES (?, ?, ?, ?)",
              (exercise_id, DEFAULT_TARGET_SETS, DEFAULT_TARGET_REPS, 135.0))
    
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

if __name__ == "__main__":
    init_database()
