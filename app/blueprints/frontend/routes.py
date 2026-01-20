from app.blueprints.frontend import frontend_bp


@frontend_bp.get("/")
def frontend_index():
    return {"module": "frontend", "message": "前台管理入口"}


@frontend_bp.get("/health")
def frontend_health():
    return {"status": "ok"}
