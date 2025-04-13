from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import os
import json
import time
import sqlite3
from datetime import datetime, timedelta
import matplotlib
matplotlib.use('Agg')  # 非交互式后端，避免需要显示界面
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import jieba
from wordcloud import WordCloud
import io
from astrbot.api.message_components import Image
import re

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


@register("astrbot_plugin_chat_stats", "User", "基于SQLite存储的群聊统计分析工具", "1.0.0")
class ChatStatsPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 获取 SQLite 数据库路径
        self.db_path = None
        self.config_file = "chat_stats_config.json"
        self.triggers = {
            "群聊排名": self.generate_chat_ranking,
            "群聊热力图": self.generate_heatmap,
            "群聊词云": self.generate_wordcloud
        }
        
    async def initialize(self):
        """初始化插件，找到SQLite数据库"""
        try:
            # 尝试找到SQLite Chat Store插件的数据库
            sqlite_plugin_config = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sqlite_chat_store_config.json")
            if os.path.exists(sqlite_plugin_config):
                with open(sqlite_plugin_config, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.db_path = config.get("db_path", None)
                    if self.db_path:
                        logger.info(f"发现SQLite聊天记录数据库: {self.db_path}")
                    else:
                        logger.warning("未在配置中找到SQLite数据库路径")
            else:
                logger.warning("未找到SQLite聊天记录插件配置文件")
                # 默认路径
                self.db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat_records.db")
                if os.path.exists(self.db_path):
                    logger.info(f"使用默认数据库路径: {self.db_path}")
                else:
                    logger.error(f"默认数据库路径不存在: {self.db_path}")
                    self.db_path = None
        except Exception as e:
            logger.error(f"初始化统计插件失败: {str(e)}")
            self.db_path = None
    
    def get_connection(self):
        """获取数据库连接"""
        if not self.db_path or not os.path.exists(self.db_path):
            return None
        try:
            return sqlite3.connect(self.db_path)
        except Exception as e:
            logger.error(f"连接数据库失败: {str(e)}")
            return None
    
    def get_today_data(self, group_id):
        """获取当天的群聊数据"""
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            # 获取今天的日期范围
            today = datetime.now().strftime('%Y-%m-%d')
            tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            
            # 查询数据
            df = pd.read_sql_query("""
                SELECT sender_id, sender_name, message, timestamp 
                FROM chat_records 
                WHERE group_id = ? AND timestamp >= ? AND timestamp < ?
                ORDER BY timestamp
            """, conn, params=(group_id, today, tomorrow))
            
            conn.close()
            
            if df.empty:
                return None
                
            # 添加小时列，用于热力图
            df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
            
            return df
        except Exception as e:
            logger.error(f"获取数据失败: {str(e)}")
            conn.close()
            return None
    
    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        """监听消息，检测触发关键词"""
        if event.get_platform_name() != "gewechat":
            return
            
        # 检查是否是群聊
        if not event.message_obj.group_id:
            return
            
        # 检查消息内容是否包含触发词
        message = event.message_str.strip()
        
        for trigger, handler in self.triggers.items():
            if trigger in message:
                group_id = event.message_obj.group_id
                result = await handler(group_id)
                if result:
                    yield result
                break
    
    async def generate_chat_ranking(self, group_id):
        """生成群聊排名条形图"""
        df = self.get_today_data(group_id)
        if df is None or df.empty:
            return AstrMessageEvent.plain_result("今天还没有聊天记录，无法生成群聊排名")
        
        # 按发送人统计消息数量
        sender_counts = df.groupby('sender_name').size().sort_values(ascending=False)
        
        # 生成条形图
        plt.figure(figsize=(10, 6))
        sender_counts.plot(kind='bar', color='skyblue')
        plt.title('今日群聊排名')
        plt.xlabel('发送人')
        plt.ylabel('消息数量')
        plt.tight_layout()
        
        # 保存到内存
        img_buf = io.BytesIO()
        plt.savefig(img_buf, format='png')
        img_buf.seek(0)
        plt.close()
        
        # 构建图片消息
        today = datetime.now().strftime('%Y-%m-%d')
        image_component = Image(img_buf.getvalue())
        
        return AstrMessageEvent.result_builder().add_component(image_component).add_plain(f"{today} 群聊排名统计").build()
    
    async def generate_heatmap(self, group_id):
        """生成群聊热力图"""
        df = self.get_today_data(group_id)
        if df is None or df.empty:
            return AstrMessageEvent.plain_result("今天还没有聊天记录，无法生成热力图")
        
        # 排序发送者按消息总数
        sender_totals = df.groupby('sender_name').size().sort_values(ascending=False)
        top_senders = sender_totals.index.tolist()
        
        # 限制最多显示10个发送者
        if len(top_senders) > 10:
            top_senders = top_senders[:10]
        
        # 生成热力图数据
        heatmap_data = []
        for sender in top_senders:
            sender_df = df[df['sender_name'] == sender]
            hourly_counts = sender_df.groupby('hour').size()
            
            # 确保所有小时都有数据
            hour_data = [hourly_counts.get(hour, 0) for hour in range(24)]
            heatmap_data.append(hour_data)
        
        # 创建热力图
        plt.figure(figsize=(12, 8))
        im = plt.imshow(heatmap_data, cmap='YlOrRd')
        
        # 设置标签
        plt.yticks(np.arange(len(top_senders)), top_senders)
        plt.xticks(np.arange(0, 24, 1), [f"{h}时" for h in range(24)])
        plt.xlabel('时间')
        plt.ylabel('发送人')
        plt.title('今日群聊热力图')
        
        # 添加颜色条
        plt.colorbar(im, label='消息数量')
        
        plt.tight_layout()
        
        # 保存到内存
        img_buf = io.BytesIO()
        plt.savefig(img_buf, format='png')
        img_buf.seek(0)
        plt.close()
        
        # 构建图片消息
        today = datetime.now().strftime('%Y-%m-%d')
        image_component = Image(img_buf.getvalue())
        
        return AstrMessageEvent.result_builder().add_component(image_component).add_plain(f"{today} 群聊热力图").build()
    
    async def generate_wordcloud(self, group_id):
        """生成群聊词云"""
        df = self.get_today_data(group_id)
        if df is None or df.empty:
            return AstrMessageEvent.plain_result("今天还没有聊天记录，无法生成词云")
        
        # 合并所有消息文本
        all_text = ' '.join(df['message'].tolist())
        
        # 过滤掉表情符号、URL等
        all_text = re.sub(r'http\S+', '', all_text)  # 移除URL
        all_text = re.sub(r'[^\w\s]', '', all_text)  # 移除标点符号
        
        # 使用jieba进行中文分词
        words = ' '.join(jieba.cut(all_text))
        
        # 生成词云
        wordcloud = WordCloud(
            font_path='/System/Library/Fonts/PingFang.ttc',  # macOS中文字体
            width=800,
            height=400,
            background_color='white',
            max_words=100,
            contour_width=1,
            contour_color='steelblue'
        ).generate(words)
        
        # 创建图像
        plt.figure(figsize=(10, 6))
        plt.imshow(wordcloud, interpolation='bilinear')
        plt.axis('off')
        plt.tight_layout()
        
        # 保存到内存
        img_buf = io.BytesIO()
        plt.savefig(img_buf, format='png')
        img_buf.seek(0)
        plt.close()
        
        # 构建图片消息
        today = datetime.now().strftime('%Y-%m-%d')
        image_component = Image(img_buf.getvalue())
        
        return AstrMessageEvent.result_builder().add_component(image_component).add_plain(f"{today} 群聊词云").build()
    
    async def terminate(self):
        """终止插件"""
        logger.info("群聊统计分析插件已终止")
