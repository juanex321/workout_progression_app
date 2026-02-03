"""Simple test to verify Reflex event handlers work."""
import reflex as rx


class SimpleState(rx.State):
    """Simple counter state for testing."""
    count: int = 0

    def increment(self):
        """Increment counter."""
        print(f"🔵 Increment called! Count is now: {self.count + 1}")
        self.count += 1


def simple_test() -> rx.Component:
    """Simple test page."""
    return rx.container(
        rx.vstack(
            rx.heading("Event Handler Test", size="7"),
            rx.text(f"Count: {SimpleState.count}", size="5"),
            rx.button(
                "Click Me!",
                on_click=SimpleState.increment,
                size="3",
                color_scheme="blue"
            ),
            spacing="4",
        ),
        padding="2rem",
    )


# Add this page to the app
app = rx.App()
app.add_page(simple_test, route="/test")
