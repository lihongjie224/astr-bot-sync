# AstrBot Gewechat 聊天记录 SQLite 存储插件

一个用于将 Gewechat 微信协议的聊天记录保存到 SQLite 数据库的 AstrBot 插件。

## 功能介绍

本插件可以自动捕获 Gewechat 协议中的微信消息，并将其存储到 SQLite 数据库中，方便后续查询和分析。主要存储以下信息：

- 群聊 ID（如果有）
- 发送人 ID
- 发送人名称
- 消息内容
- 消息时间
- 消息 ID
- 平台类型

## SQLite 数据库结构

本插件在 SQLite 中创建的表结构如下：

```sql
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

-- 索引
CREATE INDEX IF NOT EXISTS idx_group_id ON chat_records (group_id)
CREATE INDEX IF NOT EXISTS idx_sender_id ON chat_records (sender_id)
CREATE INDEX IF NOT EXISTS idx_timestamp ON chat_records (timestamp)
```

说明：
- `id`: 自增主键，唯一标识每条记录
- `group_id`: 群聊ID，如果是私聊则为空
- `sender_id`: 发送者ID，必填
- `sender_name`: 发送者名称
- `message`: 消息内容，必填
- `timestamp`: 消息时间戳，使用 ISO 格式的日期字符串
- `message_id`: 消息ID
- `platform`: 平台类型，固定为 "gewechat"

为了提高查询效率，插件会自动创建以下索引：
- `idx_group_id`: 用于按群聊ID快速查询
- `idx_sender_id`: 用于按发送者ID快速查询
- `idx_timestamp`: 用于按时间范围快速查询

## 安装步骤

1. 确保已安装 AstrBot 并正确配置 Gewechat
2. 将本插件克隆到 AstrBot 的插件目录中：

```bash
cd <AstrBot安装目录>/data/plugins/
git clone https://github.com/lihongjie224/astr-bot-sync
```

3. 重新启动 AstrBot 或在 WebUI 中重载插件

## 配置说明

插件首次加载时会自动创建默认配置文件 `sqlite_chat_store_config.json`，内容如下：

```json
{
  "db_path": "<插件目录>/chat_records.db",
  "enabled": false
}
```

你可以通过以下方式修改配置：

1. 直接编辑配置文件
2. 使用命令行方式配置（见下文）

## 使用方法

本插件提供以下命令：

### 1. 查看插件状态

```
/sqlchat_status
```

返回插件当前状态，包括：
- 插件是否启用
- 数据库连接状态
- 数据库路径
- 已存储记录数量

### 2. 启用插件

```
/sqlchat_enable
```

启用插件并连接到 SQLite 数据库。需要管理员权限。

### 3. 禁用插件

```
/sqlchat_disable
```

禁用插件并断开数据库连接。需要管理员权限。

### 4. 修改配置

```
/sqlchat_config [参数名] [参数值]
```

可配置的参数：
- `db_path`: SQLite 数据库文件路径

示例：
```
/sqlchat_config db_path /custom/path/chat_records.db
```

注意：修改配置后需要重载插件才能生效。

### 5. 查询聊天记录

```
/sqlchat_query [查询类型] [关键词/ID] [条数限制]
```

查询类型：
- `sender`: 查询特定发送者的消息
- `group`: 查询特定群组的消息
- `all`: 查询最新消息

示例：
```
/sqlchat_query sender 张三 10
/sqlchat_query group 12345678@chatroom 20
/sqlchat_query all 15
```

## 注意事项

1. 默认情况下，数据库文件会保存在插件目录下
2. 插件默认禁用，需要手动启用
3. SQLite 数据库是单文件数据库，支持并发读取但不支持高并发写入
4. 数据库文件大小无限制，但建议定期备份并清理过旧的数据

## 数据查询示例

除了使用插件提供的 `/sqlchat_query` 命令查询聊天记录外，你还可以直接使用 SQLite 命令行工具或 GUI 工具查询数据库，例如：

```bash
# 连接到数据库
sqlite3 <数据库路径>

# 查询最新10条记录
SELECT timestamp, sender_name, message, group_id FROM chat_records ORDER BY timestamp DESC LIMIT 10;

# 查询某个群的消息
SELECT timestamp, sender_name, message FROM chat_records WHERE group_id = '12345678@chatroom' ORDER BY timestamp DESC;

# 查询某人的消息
SELECT timestamp, message, group_id FROM chat_records WHERE sender_id = 'wxid_abcdefg' ORDER BY timestamp DESC;

# 按关键词搜索消息内容
SELECT timestamp, sender_name, message FROM chat_records WHERE message LIKE '%关键词%' ORDER BY timestamp DESC;
```

## 故障排除

1. 如果启用插件时提示错误，请检查数据库路径是否有写入权限
2. 如果插件已启用但没有记录被存储，请检查你使用的是否为 Gewechat 协议
3. 如需进一步调试，可查看 AstrBot 的日志文件
