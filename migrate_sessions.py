"""
Migration script to add session_number, rotation_index, and completed fields to existing sessions.
This script should be run once after updating the database schema.
"""

from db import get_session, Session
from plan import get_session_exercises


def migrate_existing_sessions():
    """
    Migrate existing sessions to the new schema by assigning session numbers
    based on their dates (oldest = 1, etc.) and calculating rotation indices.
    """
    with get_session() as db:
        # Get all sessions ordered by date
        sessions = db.query(Session).order_by(Session.date.asc()).all()
        
        if not sessions:
            print("No sessions found to migrate.")
            return
        
        print(f"Found {len(sessions)} sessions to migrate.")
        
        # Group sessions by workout_id
        sessions_by_workout = {}
        for sess in sessions:
            if sess.workout_id not in sessions_by_workout:
                sessions_by_workout[sess.workout_id] = []
            sessions_by_workout[sess.workout_id].append(sess)
        
        # Assign session numbers for each workout
        migrated_count = 0
        for workout_id, workout_sessions in sessions_by_workout.items():
            print(f"\nMigrating {len(workout_sessions)} sessions for workout_id {workout_id}")
            
            for idx, sess in enumerate(workout_sessions, start=1):
                # Calculate rotation index (cycles through 6 workout variations)
                total_workouts = 6  # Based on rotation pattern
                rotation_idx = (idx - 1) % total_workouts
                
                # Set session number and rotation index
                sess.session_number = idx
                sess.rotation_index = rotation_idx
                
                # Check if session has any sets logged - if yes, mark as completed
                # Otherwise, mark as incomplete (user can continue it)
                from db import Set
                has_sets = db.query(Set).filter(Set.session_id == sess.id).first() is not None
                sess.completed = 1 if has_sets else 0
                
                db.add(sess)
                migrated_count += 1
                
                print(f"  Session {idx}: date={sess.date}, rotation={rotation_idx}, completed={sess.completed}")
        
        db.commit()
        print(f"\n✅ Successfully migrated {migrated_count} sessions!")
        print("\nMigration complete. The app now uses session numbers instead of dates.")


if __name__ == "__main__":
    migrate_existing_sessions()
