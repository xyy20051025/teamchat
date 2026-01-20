import json
import os
from app import create_app


app = create_app()


def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    default_config = {"host": "0.0.0.0", "port": 5000, "debug": True}
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config.json: {e}")
            return default_config
    return default_config


if __name__ == "__main__":
    config = load_config()
    print(f"Starting server with config: {config}")
    app.run(
        host=config.get("host", "0.0.0.0"), 
        port=config.get("port", 5000), 
        debug=config.get("debug", True)
    )
