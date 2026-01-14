import sqlite3

conn = sqlite3.connect('workout. db')
cursor = conn.cursor()

print("=== SESSIONS ===")
for row in cursor.execute("SELECT * FROM sessions ORDER BY id DESC LIMIT 3"):
    print(row)

print("\n=== SETS (Dumbbell Lateral Raise) ===")
query = """
SELECT s.*, sess.session_number, sess.completed, sess.date
FROM sets s
JOIN sessions sess ON s.session_id = sess.id
JOIN workouts_exercises we ON s.workout_exercise_id = we.id
JOIN exercises e ON we.exercise_id = e.id
WHERE e.name LIKE '%Lateral%'
ORDER BY sess.session_number DESC, s.set_number ASC
LIMIT 10
"""
for row in cursor.execute(query):
    print(row)

print("\n=== WORKOUT_EXERCISES (Dumbbell Lateral Raise) ===")
query2 = """
SELECT we.id, e.name, we.target_sets, we.target_reps
FROM workouts_exercises we
JOIN exercises e ON we.exercise_id = e.id
WHERE e.name LIKE '%Lateral%'
"""
for row in cursor.execute(query2):
    print(row)

conn.close()