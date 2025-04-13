from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import os
import json
import time
import sqlite3
from datetime import datetime

@register("astrbot_plugin_sqlite_chat_store", "User", "存储 gewechat 聊天记录到 SQLite 数据库", "1.0.0")
class SqliteChatStorePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.db_conn = None
        self.db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat_records.db")
        self.config_file = "sqlite_chat_store_config.json"
        self.enabled = False
        
    async def initialize(self):
        """初始化 SQLite 数据库连接和配置"""
        try:
            # 读取配置文件
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.config_file)
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.db_path = config.get("db_path", self.db_path)
                    self.enabled = config.get("enabled", False)
            else:
                # 创建默认配置文件
                default_config = {
                    "db_path": self.db_path,
                    "enabled": self.enabled
                }
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=2, ensure_ascii=False)
                logger.info(f"已创建默认配置文件: {config_path}")
            
            # 初始化 SQLite 数据库
            if self.enabled:
                self.db_conn = sqlite3.connect(self.db_path)
                # 创建表（如果不存在）
                self.create_tables()
                logger.info(f"SQLite 数据库连接成功: {self.db_path}")
        except Exception as e:
            logger.error(f"初始化 SQLite 数据库连接失败: {str(e)}")
            self.enabled = False

    def create_tables(self):
        """创建 SQLite 数据表（如果不存在）"""
        try:
            cursor = self.db_conn.cursor()
            
            # 创建聊天记录表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT,
                sender_id TEXT NOT NULL,
                sender_name TEXT,
                message TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                message_id TEXT,
                platform TEXT NOT NULL
            )
            ''')
            
            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_group_id ON chat_records (group_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sender_id ON chat_records (sender_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON chat_records (timestamp)')
            
            self.db_conn.commit()
            logger.info("创建数据表和索引成功")
        except Exception as e:
            logger.error(f"创建数据表失败: {str(e)}")

    # 使用正确的监听器装饰器监听所有消息
    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        """监听并存储所有 gewechat 消息到 SQLite"""
        if not self.enabled or self.db_conn is None:
            return
        
        # 检查平台是否为 gewechat
        if event.get_platform_name() != "gewechat":
            return
        
        try:
            # 获取消息基本信息
            message_obj = event.message_obj
            sender = message_obj.sender
            
            # 准备存储数据
            timestamp = datetime.fromtimestamp(
                message_obj.timestamp / 1000 if message_obj.timestamp > 1000000000000 else message_obj.timestamp
            ).isoformat()
            
            # 插入记录到数据库
            cursor = self.db_conn.cursor()
            cursor.execute('''
            INSERT INTO chat_records (group_id, sender_id, sender_name, message, timestamp, message_id, platform)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                message_obj.group_id,
                sender.user_id,
                sender.nickname or sender.user_id,
                message_obj.message_str,
                timestamp,
                message_obj.message_id,
                "gewechat"
            ))
            self.db_conn.commit()
            logger.debug(f"存储消息到 SQLite 成功，消息ID: {message_obj.message_id}")
        except Exception as e:
            logger.error(f"存储消息到 SQLite 失败: {str(e)}")

    @filter.command("sqlchat_status")
    async def status(self, event: AstrMessageEvent):
        """查看 SQLite 聊天存储插件状态"""
        status_info = []
        status_info.append(f"SQLite 存储插件状态: {'启用' if self.enabled else '禁用'}")
        
        if self.enabled and self.db_conn is not None:
            try:
                # 检查数据库连接
                cursor = self.db_conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM chat_records")
                count = cursor.fetchone()[0]
                status_info.append(f"数据库连接: 正常")
                status_info.append(f"数据库路径: {self.db_path}")
                status_info.append(f"已存储记录数: {count}")
            except Exception as e:
                status_info.append(f"数据库状态检查失败: {str(e)}")
        else:
            status_info.append(f"数据库连接: 未初始化")
            
        yield event.plain_result("\n".join(status_info))

    @filter.command("sqlchat_enable")
    async def enable(self, event: AstrMessageEvent):
        """启用 SQLite 聊天存储插件"""
        # 检查管理员权限
        if not event.is_admin():
            yield event.plain_result("只有管理员可以执行此操作")
            return
            
        try:
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.config_file)
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                config["enabled"] = True
                
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                
                self.enabled = True
                # 初始化 SQLite 连接
                self.db_conn = sqlite3.connect(self.db_path)
                # 创建表（如果不存在）
                self.create_tables()
                yield event.plain_result("SQLite 聊天存储插件已启用")
            else:
                yield event.plain_result("配置文件不存在，请先重载插件初始化配置")
        except Exception as e:
            yield event.plain_result(f"启用失败: {str(e)}")

    @filter.command("sqlchat_disable")
    async def disable(self, event: AstrMessageEvent):
        """禁用 SQLite 聊天存储插件"""
        # 检查管理员权限
        if not event.is_admin():
            yield event.plain_result("只有管理员可以执行此操作")
            return
            
        try:
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.config_file)
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                config["enabled"] = False
                
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                
                self.enabled = False
                # 关闭数据库连接
                if self.db_conn is not None:
                    self.db_conn.close()
                    self.db_conn = None
                yield event.plain_result("SQLite 聊天存储插件已禁用")
            else:
                yield event.plain_result("配置文件不存在，请先重载插件初始化配置")
        except Exception as e:
            yield event.plain_result(f"禁用失败: {str(e)}")

    @filter.command("sqlchat_config")
    async def config(self, event: AstrMessageEvent):
        """配置 SQLite 聊天存储插件"""
        # 检查管理员权限
        if not event.is_admin():
            yield event.plain_result("只有管理员可以执行此操作")
            return
        
        message_parts = event.message_str.split()
        if len(message_parts) < 3:
            yield event.plain_result("使用方法: /sqlchat_config [db_path] <新值>")
            return
            
        param = message_parts[1]
        value = message_parts[2]
        
        try:
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.config_file)
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                if param == "db_path":
                    config["db_path"] = value
                    self.db_path = value
                else:
                    yield event.plain_result(f"未知参数: {param}")
                    return
                
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                
                yield event.plain_result(f"配置已更新: {param} = {value}")
                yield event.plain_result("请重载插件使配置生效")
            else:
                yield event.plain_result("配置文件不存在，请先重载插件初始化配置")
        except Exception as e:
            yield event.plain_result(f"配置失败: {str(e)}")
    
    @filter.command("sqlchat_query")
    async def query(self, event: AstrMessageEvent):
        """查询聊天记录"""
        if not self.enabled or self.db_conn is None:
            yield event.plain_result("SQLite 聊天存储插件未启用")
            return
            
        message_parts = event.message_str.split()
        if len(message_parts) < 2:
            yield event.plain_result("使用方法: /sqlchat_query [sender|group|all] [关键词/ID（可选）] [条数限制（默认10）]")
            return
            
        query_type = message_parts[1]
        keyword = message_parts[2] if len(message_parts) > 2 else None
        limit = int(message_parts[3]) if len(message_parts) > 3 and message_parts[3].isdigit() else 10
        
        try:
            cursor = self.db_conn.cursor()
            results = []
            
            if query_type == "sender" and keyword:
                # 查询特定发送者的消息
                cursor.execute('''
                SELECT timestamp, sender_name, message, group_id FROM chat_records 
                WHERE sender_id = ? OR sender_name LIKE ? 
                ORDER BY timestamp DESC LIMIT ?
                ''', (keyword, f"%{keyword}%", limit))
                results = cursor.fetchall()
                
            elif query_type == "group" and keyword:
                # 查询特定群组的消息
                cursor.execute('''
                SELECT timestamp, sender_name, message, group_id FROM chat_records 
                WHERE group_id = ? 
                ORDER BY timestamp DESC LIMIT ?
                ''', (keyword, limit))
                results = cursor.fetchall()
                
            elif query_type == "all":
                # 查询最新消息
                cursor.execute('''
                SELECT timestamp, sender_name, message, group_id FROM chat_records 
                ORDER BY timestamp DESC LIMIT ?
                ''', (limit,))
                results = cursor.fetchall()
                
            else:
                yield event.plain_result("未知查询类型，使用方法: /sqlchat_query [sender|group|all] [关键词/ID（可选）] [条数限制（默认10）]")
                return
                
            if not results:
                yield event.plain_result("未找到匹配的聊天记录")
                return
                
            formatted_results = []
            for timestamp, sender_name, message, group_id in results:
                group_info = f"[群:{group_id}]" if group_id else "[私聊]"
                formatted_results.append(f"{timestamp} {group_info} {sender_name}: {message}")
                
            yield event.plain_result("\n\n".join(formatted_results))
            
        except Exception as e:
            yield event.plain_result(f"查询失败: {str(e)}")
    
    async def terminate(self):
        """终止插件时关闭数据库连接"""
        if self.db_conn is not None:
            try:
                self.db_conn.close()
                logger.info("SQLite 数据库连接已关闭")
            except Exception as e:
                logger.error(f"关闭 SQLite 数据库连接失败: {str(e)}")
