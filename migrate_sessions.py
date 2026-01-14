"""
Safe migration script with automatic backup and rollback.
This script migrates existing sessions to add session numbers and rotation indices.
"""
from db import get_session, Session, Set
from backup_db import create_backup, restore_backup
import sys

def check_schema_compatibility():
    """Check if the database has the new schema columns."""
    with get_session() as db:
        try:
            # Try to query the new columns
            db.query(Session.session_number).first()
            db.query(Session.rotation_index).first()
            db.query(Session.completed).first()
            return True
        except Exception as e:
            print(f"⚠️  Schema compatibility issue: {e}")
            return False

def migrate_existing_sessions():
    """
    Migrate existing sessions to the new schema.
    Creates automatic backup before starting.
    """
    print("\n🔄 Starting safe database migration...")
    
    # Step 1: Create backup
    print("\n📦 Step 1/4: Creating backup...")
    backup_path = create_backup(reason="pre_migration")
    if not backup_path:
        print("❌ Cannot proceed without backup!")
        return False
    
    # Step 2: Check schema compatibility
    print("\n🔍 Step 2/4: Checking schema compatibility...")
    if not check_schema_compatibility():
        print("❌ Database schema doesn't have required columns!")
        print("   Run 'alembic upgrade head' first to add the new columns.")
        return False
    
    # Step 3: Migrate data
    print("\n📝 Step 3/4: Migrating session data...")
    try:
        with get_session() as db:
            sessions = db.query(Session).order_by(Session.date.asc()).all()
            
            if not sessions:
                print("⚠️  No sessions found to migrate.")
                return True
            
            print(f"Found {len(sessions)} sessions to migrate.")
            
            # Group by workout_id
            sessions_by_workout = {}
            for sess in sessions:
                if sess.workout_id not in sessions_by_workout:
                    sessions_by_workout[sess.workout_id] = []
                sessions_by_workout[sess.workout_id].append(sess)
            
            migrated_count = 0
            for workout_id, workout_sessions in sessions_by_workout.items():
                print(f"\n  Migrating {len(workout_sessions)} sessions for workout_id {workout_id}")
                
                for idx, sess in enumerate(workout_sessions, start=1):
                    # Skip if already migrated (session_number > 0 indicates migration already done)
                    if sess.session_number and sess.session_number > 1:
                        print(f"    Session {sess.id} already migrated (session_number={sess.session_number})")
                        continue
                    
                    # Calculate rotation index
                    total_workouts = 6
                    rotation_idx = (idx - 1) % total_workouts
                    
                    # Set fields
                    sess.session_number = idx
                    sess.rotation_index = rotation_idx
                    
                    # Check for logged sets
                    has_sets = db.query(Set).filter(Set.session_id == sess.id).first() is not None
                    sess.completed = 1 if has_sets else 0
                    
                    db.add(sess)
                    migrated_count += 1
                    
                    print(f"    ✓ Session {idx}: date={sess.date}, rotation={rotation_idx}, completed={sess.completed}, sets={has_sets}")
            
            db.commit()
            print(f"\n✅ Successfully migrated {migrated_count} sessions!")
            
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        print(f"🔄 Rolling back to backup: {backup_path}")
        restore_backup(backup_path)
        return False
    
    # Step 4: Verify migration
    print("\n✅ Step 4/4: Verifying migration...")
    with get_session() as db:
        sessions = db.query(Session).all()
        print(f"   Total sessions: {len(sessions)}")
        completed = sum(1 for s in sessions if s.completed)
        print(f"   Completed: {completed}")
        print(f"   In progress: {len(sessions) - completed}")
    
    print("\n🎉 Migration complete! Your data is safe.")
    print(f"💾 Backup saved at: {backup_path}")
    return True

if __name__ == "__main__":
    success = migrate_existing_sessions()
    sys.exit(0 if success else 1)

