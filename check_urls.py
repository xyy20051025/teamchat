from app import create_app

app = create_app()
with app.app_context():
    print("Rules for backend.get_room_members:")
    try:
        print(app.url_map.iter_rules('backend.get_room_members'))
        found = False
        for rule in app.url_map.iter_rules():
            if rule.endpoint == 'backend.get_room_members':
                print(f"FOUND: {rule}")
                found = True
        if not found:
            print("NOT FOUND in iteration")
    except Exception as e:
        print(f"Error: {e}")

    print("\nAll backend rules:")
    for rule in app.url_map.iter_rules():
        if rule.endpoint.startswith('backend.'):
            print(f"{rule.endpoint}: {rule}")
