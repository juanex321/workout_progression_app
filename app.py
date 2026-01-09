from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
import json
import os

app = Flask(__name__)

# Data storage file
DATA_FILE = 'workouts.json'

def load_workouts():
    """Load workouts from JSON file."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_workouts(data):
    """Save workouts to JSON file."""
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')

@app.route('/api/workouts', methods=['GET', 'POST'])
def workouts():
    """Get or add workouts."""
    data = load_workouts()
    
    if request.method == 'POST':
        workout = request.json
        workout_id = datetime.now().isoformat()
        workout['id'] = workout_id
        workout['date'] = workout.get('date', datetime.now().strftime('%Y-%m-%d'))
        data[workout_id] = workout
        save_workouts(data)
        return jsonify(workout), 201
    
    return jsonify(list(data.values()))

@app.route('/api/workouts/<workout_id>', methods=['GET', 'PUT', 'DELETE'])
def workout_detail(workout_id):
    """Get, update, or delete a specific workout."""
    data = load_workouts()
    
    if request.method == 'GET':
        if workout_id in data:
            return jsonify(data[workout_id])
        return jsonify({'error': 'Workout not found'}), 404
    
    elif request.method == 'PUT':
        if workout_id in data:
            data[workout_id].update(request.json)
            save_workouts(data)
            return jsonify(data[workout_id])
        return jsonify({'error': 'Workout not found'}), 404
    
    elif request.method == 'DELETE':
        if workout_id in data:
            del data[workout_id]
            save_workouts(data)
            return jsonify({'success': True}), 204
        return jsonify({'error': 'Workout not found'}), 404

@app.route('/api/stats', methods=['GET'])
def stats():
    """Get workout statistics."""
    data = load_workouts()
    workouts_list = list(data.values())
    
    if not workouts_list:
        return jsonify({
            'total_workouts': 0,
            'total_volume': 0,
            'avg_reps': 0,
            'avg_sets': 0
        })
    
    total_volume = sum(w.get('sets', 0) * w.get('reps', 0) * w.get('weight', 0) for w in workouts_list)
    avg_reps = sum(w.get('reps', 0) for w in workouts_list) / len(workouts_list)
    avg_sets = sum(w.get('sets', 0) for w in workouts_list) / len(workouts_list)
    
    return jsonify({
        'total_workouts': len(workouts_list),
        'total_volume': round(total_volume, 2),
        'avg_reps': round(avg_reps, 1),
        'avg_sets': round(avg_sets, 1)
    })

if __name__ == '__main__':
    app.run(debug=True)
