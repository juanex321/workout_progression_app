# Reflex Migration Guide

This document explains how to run both the Streamlit and Reflex versions side-by-side.

## What's Different?

### Streamlit (Current)
- Uses `st.markdown()` with HTML injection for custom layouts
- **Limited**: Can't easily wrap muscle groups with colored borders
- CSS hacks required for custom styling

### Reflex (New)
- Proper component-based architecture
- **Full control**: Muscle groups wrapped in colored divs natively
- Clean Python code, no HTML injection
- Better state management

## Running Both Apps

### Keep Running Streamlit (Port 8501)
```bash
# Terminal 1 - Your existing app
streamlit run app.py
```
Visit: http://localhost:8501

### Try Reflex (Port 3000)
```bash
# Terminal 2 - New Reflex app
cd reflex_app
reflex init  # First time only
reflex run
```
Visit: http://localhost:3000

## Key Improvements in Reflex

### 1. Proper Component Wrapping
**Streamlit (hacky):**
```python
st.markdown(f'<div class="wrapper {rir_class}">', unsafe_allow_html=True)
st.markdown("Hamstrings")
# ... exercise displays ...
st.markdown('</div>', unsafe_allow_html=True)  # Hope it closes correctly!
```

**Reflex (clean):**
```python
rx.box(
    muscle_group_header(),
    rx.foreach(exercises, exercise_sets),
    feedback_form(),
    border=f"3px solid {get_rir_color(rir)}",
    border_radius="12px",
    padding="1rem"
)
```

### 2. Better State Management
- Streamlit: Session state with weird rerun behavior
- Reflex: Proper reactive state (like React hooks)

### 3. Easier Styling
- Streamlit: Inject CSS strings, fight with !important
- Reflex: Props directly on components

## What's Shared?

These files are used by BOTH apps (no duplication):
- ✅ `db.py` - Database models
- ✅ `progression.py` - Progression logic
- ✅ `rir_progression.py` - RIR calculations
- ✅ `services.py` - Business logic
- ✅ `plan.py` - Workout planning

Only the UI layer changes!

## Migration Status

- [x] Basic proof of concept
- [ ] Exercise set inputs with state
- [ ] Log button functionality
- [ ] Feedback forms
- [ ] Session navigation
- [ ] Mobile responsive styling
- [ ] Deploy to production

## Switching to Reflex

When you're ready to switch:
1. Test Reflex version thoroughly
2. Update deployment to run `reflex run` instead of `streamlit run`
3. Archive `app.py` (keep for reference)
4. Done!

## Rollback Plan

If Reflex doesn't work out:
1. Delete `reflex_app/` folder
2. Keep using `app.py`
3. No harm done - all your logic is intact!
