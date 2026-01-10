# Copilot Instructions for Workout Progression App

## Project Overview

This is a **Workout Progression App** built with Streamlit that helps users track their workout progress, manage exercises, and follow progressive overload principles.

## Tech Stack

- **Frontend/UI**: Streamlit
- **Database**: SQLite with SQLAlchemy ORM
- **Data Processing**: Pandas
- **Python Version**: 3.12+

## Project Structure

- `app.py` - Main Streamlit application with UI and workout tracking functionality
- `db.py` - SQLAlchemy database models (Program, Workout, Exercise, Session, Set, WorkoutExercise)
- `services.py` - Business logic services for session and set management
- `progression.py` - Weight and rep recommendation algorithm
- `plan.py` - Workout planning logic
- `init_db.py` - Database initialization script
- `add_exercises.py` - Exercise data management
- `workout.db` - SQLite database (excluded from version control)

## Development Guidelines

### Running the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize the database (first time only)
python init_db.py

# Run the application
streamlit run app.py
```

### Database

- The app uses SQLite with SQLAlchemy ORM
- Database file: `workout.db` (gitignored)
- Models: Program, Workout, Exercise, WorkoutExercise, Session, Set
- Use context managers from `db.get_session()` for all database operations
- Always close sessions properly to avoid locks

### Code Style

- Use 4 spaces for indentation
- Follow PEP 8 naming conventions
- Use descriptive variable names
- Add docstrings for functions that implement complex logic
- Keep functions focused and single-purpose

### Streamlit Best Practices

- Use `st.session_state` for managing application state
- Inject custom CSS via `inject_css()` function for styling
- Use `st.rerun()` to refresh the UI after state changes
- Keep UI logic in `app.py`, business logic in separate modules

### Database Operations

- Always use context managers: `with get_session() as db:`
- Commit transactions explicitly when making changes
- Use relationships defined in models rather than manual joins
- Keep database queries in service functions, not in UI code

### Progressive Overload Logic

- The `progression.py` module handles weight/rep recommendations
- Recommendations are based on past performance data
- Follow the principle: increase reps first, then weight

### Key Patterns to Follow

1. **Separation of Concerns**: Keep UI (`app.py`), business logic (`services.py`), and data models (`db.py`) separate
2. **Session Management**: Use the session context manager pattern for all DB operations
3. **State Management**: Use Streamlit's session state for UI state that persists between reruns
4. **Error Handling**: Handle database errors gracefully and provide user feedback

### What NOT to Do

- Don't add hardcoded data in the application code
- Don't commit `workout.db` to version control
- Don't bypass the SQLAlchemy ORM with raw SQL unless absolutely necessary
- Don't mix UI logic with database operations
- Don't use global variables for state management (use `st.session_state`)

## Testing

Currently, this project does not have automated tests. When adding tests:
- Use pytest as the testing framework
- Create a `tests/` directory
- Use an in-memory SQLite database for testing
- Mock Streamlit components where necessary

## Dependencies

Keep dependencies minimal. Current dependencies:
- streamlit - Web UI framework
- pandas - Data manipulation
- SQLAlchemy - ORM for database operations

Before adding new dependencies, consider if existing ones can solve the problem.

## Common Tasks

### Adding a New Exercise
Use the database models to insert exercises via the SQLAlchemy session.

### Modifying the Progression Algorithm
Edit `progression.py` - the `recommend_weights_and_reps` function implements the core logic.

### Adding UI Components
Follow the existing pattern in `app.py` with helper functions and CSS injection.

### Database Schema Changes
1. Update models in `db.py`
2. Update `init_db.py` if needed
3. Consider migration strategy for existing databases
