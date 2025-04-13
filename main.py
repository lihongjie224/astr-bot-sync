from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from elasticsearch import Elasticsearch
import os
import json
import time
from datetime import datetime
from astrbot.api.event import platform_adapter_type, event_message_type
from astrbot.api.platform import PlatformAdapterType
from astrbot.api.event import EventMessageType

@register("helloworld", "YourName", "一个简单的 Hello World 插件", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""
    
    # 注册指令的装饰器。指令名为 helloworld。注册成功后，发送 `/helloworld` 就会触发这个指令，并回复 `你好, {user_name}!`
    @filter.command("helloworld")
    async def helloworld(self, event: AstrMessageEvent):
        """这是一个 hello world 指令""" # 这是 handler 的描述，将会被解析方便用户了解插件内容。建议填写。
        user_name = event.get_sender_name()
        message_str = event.message_str # 用户发的纯文本消息字符串
        message_chain = event.get_messages() # 用户所发的消息的消息链 # from astrbot.api.message_components import *
        logger.info(message_chain)
        yield event.plain_result(f"Hello, {user_name}, 你发了 {message_str}!") # 发送一条纯文本消息

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""


@register("astrbot_plugin_es_chat_store", "User", "存储 gewechat 聊天记录到 Elasticsearch", "1.0.0")
class EsChatStorePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.es_client = None
        self.es_index = "gewechat_chat_records"
        self.es_host = "http://localhost:9200"  # 默认 ES 地址
        self.config_file = "es_chat_store_config.json"
        self.enabled = False
        
    async def initialize(self):
        """初始化 Elasticsearch 连接和配置"""
        try:
            # 读取配置文件
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.config_file)
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.es_host = config.get("es_host", self.es_host)
                    self.es_index = config.get("es_index", self.es_index)
                    self.enabled = config.get("enabled", False)
            else:
                # 创建默认配置文件
                default_config = {
                    "es_host": self.es_host,
                    "es_index": self.es_index,
                    "enabled": self.enabled
                }
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=2, ensure_ascii=False)
                logger.info(f"已创建默认配置文件: {config_path}")
            
            # 初始化 ES 客户端 
            if self.enabled:
                self.es_client = Elasticsearch(self.es_host)
                # 检查连接
                if self.es_client.ping():
                    logger.info(f"Elasticsearch 连接成功: {self.es_host}")
                    # 检查索引是否存在
                    if not self.es_client.indices.exists(index=self.es_index):
                        # 创建索引
                        self.create_index()
                else:
                    logger.error(f"Elasticsearch 连接失败: {self.es_host}")
                    self.enabled = False
        except Exception as e:
            logger.error(f"初始化 Elasticsearch 连接失败: {str(e)}")
            self.enabled = False

    def create_index(self):
        """创建 Elasticsearch 索引和映射"""
        try:
            mappings = {
                "mappings": {
                    "properties": {
                        "group_id": {"type": "keyword"},  # 群聊ID
                        "sender_id": {"type": "keyword"},  # 发送者ID
                        "sender_name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},  # 发送者名称
                        "message": {"type": "text", "analyzer": "ik_max_word"},  # 消息内容
                        "timestamp": {"type": "date"},  # 消息时间戳
                        "message_id": {"type": "keyword"},  # 消息ID
                        "platform": {"type": "keyword"},  # 平台类型
                    }
                }
            }
            self.es_client.indices.create(index=self.es_index, body=mappings)
            logger.info(f"创建索引成功: {self.es_index}")
        except Exception as e:
            logger.error(f"创建索引失败: {str(e)}")

    # 使用 platform_adapter_type 装饰器，只监听 Gewechat 平台的消息
    @platform_adapter_type(PlatformAdapterType.GEWECHAT)
    @event_message_type(EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        """监听并存储所有 gewechat 消息到 Elasticsearch"""
        if not self.enabled or self.es_client is None:
            return
        
        try:
            # 获取消息基本信息
            message_obj = event.message_obj
            sender = message_obj.sender
            
            # 准备存储数据
            doc = {
                "group_id": message_obj.group_id,  # 如果是群聊，这里会有值
                "sender_id": sender.user_id,
                "sender_name": sender.nickname or sender.user_id,
                "message": message_obj.message_str,
                "timestamp": datetime.fromtimestamp(message_obj.timestamp / 1000 if message_obj.timestamp > 1000000000000 else message_obj.timestamp),
                "message_id": message_obj.message_id,
                "platform": "gewechat"
            }
            
            # 存储到 ES
            result = self.es_client.index(index=self.es_index, document=doc)
            logger.debug(f"存储消息到 ES 成功: {result.get('_id')}")
        except Exception as e:
            logger.error(f"存储消息到 ES 失败: {str(e)}")

    @filter.command("eschat_status")
    async def status(self, event: AstrMessageEvent):
        """查看 ES 聊天存储插件状态"""
        status_info = []
        status_info.append(f"ES 存储插件状态: {'启用' if self.enabled else '禁用'}")
        
        if self.enabled and self.es_client is not None:
            try:
                # 检查 ES 连接
                if self.es_client.ping():
                    status_info.append(f"ES 连接: 正常")
                    # 获取索引状态
                    if self.es_client.indices.exists(index=self.es_index):
                        # 获取文档数量
                        count = self.es_client.count(index=self.es_index)
                        status_info.append(f"索引 {self.es_index}: 存在")
                        status_info.append(f"已存储记录数: {count.get('count', 0)}")
                    else:
                        status_info.append(f"索引 {self.es_index}: 不存在")
                else:
                    status_info.append(f"ES 连接: 失败")
            except Exception as e:
                status_info.append(f"ES 状态检查失败: {str(e)}")
        else:
            status_info.append(f"ES 连接: 未初始化")
            
        yield event.plain_result("\n".join(status_info))

    @filter.command("eschat_enable")
    async def enable(self, event: AstrMessageEvent):
        """启用 ES 聊天存储插件"""
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
                # 初始化 ES 客户端
                self.es_client = Elasticsearch(self.es_host)
                if self.es_client.ping():
                    # 检查索引是否存在
                    if not self.es_client.indices.exists(index=self.es_index):
                        # 创建索引
                        self.create_index()
                    yield event.plain_result("ES 聊天存储插件已启用")
                else:
                    yield event.plain_result(f"启用失败: 无法连接到 Elasticsearch ({self.es_host})")
            else:
                yield event.plain_result("配置文件不存在，请先重载插件初始化配置")
        except Exception as e:
            yield event.plain_result(f"启用失败: {str(e)}")

    @filter.command("eschat_disable")
    async def disable(self, event: AstrMessageEvent):
        """禁用 ES 聊天存储插件"""
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
                self.es_client = None
                yield event.plain_result("ES 聊天存储插件已禁用")
            else:
                yield event.plain_result("配置文件不存在，请先重载插件初始化配置")
        except Exception as e:
            yield event.plain_result(f"禁用失败: {str(e)}")

    @filter.command("eschat_config")
    async def config(self, event: AstrMessageEvent):
        """配置 ES 聊天存储插件"""
        # 检查管理员权限
        if not event.is_admin():
            yield event.plain_result("只有管理员可以执行此操作")
            return
        
        message_parts = event.message_str.split()
        if len(message_parts) < 3:
            yield event.plain_result("使用方法: /eschat_config [es_host|es_index] <新值>")
            return
            
        param = message_parts[1]
        value = message_parts[2]
        
        try:
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.config_file)
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                if param == "es_host":
                    config["es_host"] = value
                    self.es_host = value
                elif param == "es_index":
                    config["es_index"] = value
                    self.es_index = value
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
    
    async def terminate(self):
        """终止插件时关闭 ES 连接"""
        if self.es_client is not None:
            try:
                self.es_client.close()
                logger.info("ES 客户端已关闭")
            except Exception as e:
                logger.error(f"关闭 ES 客户端失败: {str(e)}")
