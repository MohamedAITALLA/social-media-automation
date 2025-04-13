from app import create_app
from flask import Flask, render_template, redirect, url_for, flash

# Create the Flask application instance
app = create_app()

# Make the application available to Vercel
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False) 