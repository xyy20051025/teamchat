from app import create_app
from app.extensions import db
from app.models import Menu

app = create_app()

def migrate_menus():
    with app.app_context():
        # Clear existing menus to avoid duplicates during dev
        # db.session.query(Menu).delete()
        
        menus = [
            {'name': '控制台', 'url': 'backend.backend_index', 'icon': 'layui-icon-console', 'order': 1},
            {'name': '用户管理', 'url': 'backend.user_list', 'icon': 'layui-icon-user', 'order': 2},
            {'name': '房间管理', 'url': 'backend.room_list', 'icon': 'layui-icon-group', 'order': 3},
            {'name': '消息文件', 'url': 'backend.file_list', 'icon': 'layui-icon-file', 'order': 4},
            {'name': 'ws服务器管理', 'url': 'backend.server_list', 'icon': 'layui-icon-server', 'order': 5},
            {'name': '接口管理', 'url': 'backend.interface_list', 'icon': 'layui-icon-link', 'order': 6},
            {'name': 'AI模型引擎', 'url': 'backend.ai_model_list', 'icon': 'layui-icon-engine', 'order': 7},
            {'name': '菜单管理', 'url': 'backend.menu_list', 'icon': 'layui-icon-app', 'order': 8},
            {'name': '角色管理', 'url': 'backend.role_list', 'icon': 'layui-icon-user', 'order': 9},
            {'name': '管理员管理', 'url': 'backend.admin_list', 'icon': 'layui-icon-username', 'order': 10},
            {'name': 'AI分析与报告', 'url': 'backend.ai_analysis', 'icon': 'layui-icon-chart-screen', 'order': 11},
        ]
        for m_data in menus:
            existing = Menu.query.filter_by(url=m_data['url']).first()
            if not existing:
                menu = Menu(
                    name=m_data['name'],
                    url=m_data['url'],
                    icon=m_data['icon'],
                    order=m_data['order']
                )
                db.session.add(menu)
                print(f"Added menu: {m_data['name']}")
            else:
                existing.name = m_data['name']
                existing.icon = m_data['icon']
                existing.order = m_data['order']
                print(f"Updated menu: {m_data['name']}")
        
        db.session.commit()
        print("Menu migration completed.")

if __name__ == '__main__':
    migrate_menus()
