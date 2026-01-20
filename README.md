# QuLao Business Management System (TeamChat)

QuLao 业务管理系统（内部代号：TeamChat）是一个基于 Python Flask 开发的团队协作与即时通讯平台。集成了实时聊天、好友管理、群组互动以及后台管理系统。

## 📋 基本信息 (Basic Information)

- **项目名称**: QuLao 业务管理系统 (TeamChat)
- **开发语言**: Python 3.11+
- **核心框架**: Flask (Backend)
- **前端技术**: Bootstrap (前台), Layui (后台), jQuery, WebSocket
- **数据库**: SQLite (通过 Flask-SQLAlchemy 管理)
- **实时通信**: Flask-Sock (WebSocket)

## 🛠️ 环境要求 (Environment)

本项目在 Python 3 虚拟环境下开发和运行。

- **操作系统**: Windows / Linux / macOS
- **Python 版本**: Python 3.10 或更高版本 (推荐 3.11)
- **依赖包**: 见 `requirements.txt`

## 💻 开发与部署 (Development & Deployment)

### 1. 环境准备

建议使用 Python 虚拟环境来管理项目依赖，避免环境冲突。

```bash
# 1. 创建虚拟环境 (如果尚未创建)
python -m venv venv

# 2. 激活虚拟环境
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

### 2. 安装依赖

在激活的虚拟环境中安装项目所需的 Python 库：

```bash
pip install -r requirements.txt
```

### 3. 数据库初始化

项目首次运行前需要初始化数据库。

```bash
# 初始化数据库结构及基础数据
python init_db.py

# 更新数据库（如添加管理员表、新字段等）
python update_db.py
```

*注意：`init_db.py` 会创建 `database/quliao.db` 文件。`update_db.py` 用于后续的数据迁移或补丁。*

## 🚀 启动服务器 (Start Server)

使用 `run.py` 启动 Flask 开发服务器。

```bash
python run.py
```

服务器启动后，默认监听 `0.0.0.0:5000`。

- **前台访问**: [http://localhost:5000](http://localhost:5000)
- **后台管理**: [http://localhost:5000/admin](http://localhost:5000/admin)
  - 默认管理员账号: `admin`
  - 默认管理员密码: `admin888`

### 配置文件 (Config)

项目根目录下可创建 `config.json` 文件自定义启动参数（可选）：

```json
{
    "host": "0.0.0.0",
    "port": 5000,
    "debug": true
}
```

## 📂 项目结构 (Project Structure)

```text
teamchat/
├── app/
│   ├── blueprints/         # 路由蓝图 (Backend/Frontend)
│   ├── static/             # 静态资源 (CSS, JS, Images, Audio)
│   ├── templates/          # HTML 模板
│   ├── __init__.py         # App 工厂函数
│   ├── models.py           # 数据库模型 (User, Room, Message, etc.)
│   └── extensions.py       # 扩展初始化 (DB, Socket)
├── database/               # SQLite 数据库文件
├── venv/                   # Python 虚拟环境
├── init_db.py              # 数据库初始化脚本
├── update_db.py            # 数据库更新脚本
├── run.py                  # 项目启动入口
├── requirements.txt        # 项目依赖列表
└── README.md               # 项目说明文档
```

## 📝 运维与管理 (Operations)

- **日志查看**: 服务器运行日志直接输出在控制台。
- **数据备份**: 定期备份 `database/quliao.db` 文件即可。
- **后台管理**: 登录后台可进行用户封禁/解封、查看系统统计数据等操作。
