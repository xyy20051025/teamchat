from app.blueprints.backend import backend_bp


@backend_bp.get("/")
def backend_index():
    return {"module": "backend", "message": "后台系统管理入口"}


@backend_bp.get("/health")
def backend_health():
    return {"status": "ok"}
