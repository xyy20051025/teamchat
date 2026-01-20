from app import create_app, db
from app.models import Menu

app = create_app()
with app.app_context():
    existing = Menu.query.filter_by(name='数据大屏').first()
    if not existing:
        # Find max order
        max_order = db.session.query(db.func.max(Menu.order)).scalar() or 0
        new_menu = Menu(
            name='数据大屏',
            url='backend.dashboard',
            icon='layui-icon-chart-screen',
            order=1 # Put it near top
        )
        # Shift others down if needed, or just let it be 1. 
        # Actually let's just make it order 1 and re-sort others or just let it be.
        # If I want it at the top, I should probably check if order 1 is taken.
        # But usually menu sorting is just ASC.
        
        db.session.add(new_menu)
        db.session.commit()
        print("Menu '数据大屏' added successfully.")
    else:
        print("Menu '数据大屏' already exists.")
