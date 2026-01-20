from app import create_app
from app.extensions import db
from app.models import Menu, Role

app = create_app()

def init_menus():
    with app.app_context():
        db.create_all()
        
        # Define initial menus
        initial_menus = [
            {'name': '控制台', 'icon': 'layui-icon-home', 'url': 'backend.backend_index', 'order': 1},
            {'name': '用户管理', 'icon': 'layui-icon-user', 'url': 'backend.user_list', 'order': 2},
            {'name': '房间管理', 'icon': 'layui-icon-group', 'url': 'backend.room_list', 'order': 3},
            {'name': '群文件管理', 'icon': 'layui-icon-file', 'url': 'backend.file_list', 'order': 4},
            {'name': 'ws服务器管理', 'icon': 'layui-icon-server', 'url': 'backend.server_list', 'order': 5},
            {'name': '接口管理', 'icon': 'layui-icon-app', 'url': 'backend.interface_list', 'order': 6},
            {'name': 'AI模型引擎', 'icon': 'layui-icon-engine', 'url': 'backend.ai_model_list', 'order': 7},
            {'name': '菜单管理', 'icon': 'layui-icon-list', 'url': 'backend.menu_list', 'order': 8},
            {'name': '角色管理', 'icon': 'layui-icon-username', 'url': 'backend.role_list', 'order': 9}
        ]
        
        for m_data in initial_menus:
            menu = Menu.query.filter_by(url=m_data['url']).first()
            if not menu:
                menu = Menu(
                    name=m_data['name'],
                    icon=m_data['icon'],
                    url=m_data['url'],
                    order=m_data['order']
                )
                db.session.add(menu)
                print(f"Added menu: {m_data['name']}")
            else:
                # Update existing if needed
                menu.name = m_data['name']
                menu.icon = m_data['icon']
                menu.order = m_data['order']
                print(f"Updated menu: {m_data['name']}")
        
        db.session.commit()
        print("Menu initialization completed.")

if __name__ == '__main__':
    init_menus()
