import reflex as rx

config = rx.Config(
    app_name="workout_app",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)