# check_routes.py
from app import create_app

app = create_app()

with app.test_request_context():
    print("Available routes:")
    for rule in app.url_map.iter_rules():
        print(f"{rule.endpoint}: {rule.rule}") 