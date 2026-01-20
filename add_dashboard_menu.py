
from app import create_app, db
from app.models import Menu

app = create_app()

with app.app_context():
    # Check if dashboard menu exists
    dashboard_menu = Menu.query.filter_by(url='backend.dashboard').first()
    
    if not dashboard_menu:
        print("Adding '数据大屏' menu...")
        # Find the highest order to put it at the top or appropriate place.
        # User said: "需要在后台管理中新增数字大屏功能模块" and "需要通过菜单管理实现上述功能的管理".
        # Let's put it at order 1, shifting others if needed, or just order 1 if others are higher.
        
        # Let's just use order 0 or 1.
        menu = Menu(
            name='数据大屏',
            url='backend.dashboard',
            icon='layui-icon-chart-screen', # Assuming this icon exists or similar
            order=1
        )
        db.session.add(menu)
        db.session.commit()
        print("Menu '数据大屏' added.")
    else:
        print("Menu '数据大屏' already exists.")
