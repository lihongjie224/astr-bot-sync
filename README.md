# AstrBot 聊天工具集

一个用于 AstrBot 的聊天工具集合，包含 **SQLite 聊天记录存储插件** 和 **群聊统计分析插件**。

## 插件概览

本工具集包含两个相互协作的插件：

1. **SQLite 聊天记录存储插件**：捕获并存储 Gewechat 协议的微信消息到 SQLite 数据库
2. **群聊统计分析插件**：基于存储的聊天数据，提供群聊排名、热力图和词云等数据可视化功能

## 功能介绍

### SQLite 聊天记录存储插件

该插件可以自动捕获 Gewechat 协议中的微信消息，并将其存储到 SQLite 数据库中，方便后续查询和分析。主要存储以下信息：

- 群聊 ID（如果有）
- 发送人 ID
- 发送人名称
- 消息内容
- 消息时间
- 消息 ID
- 平台类型

#### SQLite 数据库结构

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

### 群聊统计分析插件

基于存储的聊天数据，自动监听群聊中的特定关键词，并生成对应的统计图表：

1. **群聊排名**：当检测到消息中包含"群聊排名"关键词时，自动生成当天该群聊下按照发送人维度统计的消息数量条形图。
2. **群聊热力图**：当检测到消息中包含"群聊热力图"关键词时，生成当天该群聊下按照小时维度每个发送人在每个小时内发送消息的热力图。
3. **群聊词云**：当检测到消息中包含"群聊词云"关键词时，生成当天该群聊下的聊天内容词云图。

## 安装步骤

1. 确保已安装 AstrBot 并正确配置 Gewechat
2. 将本插件克隆到 AstrBot 的插件目录中：

```bash
cd <AstrBot安装目录>/data/plugins/
git clone https://github.com/lihongjie224/astr-bot-sync
```

3. 安装插件依赖：

```bash
cd <AstrBot安装目录>/data/plugins/astr-bot-sync
pip install -r requirements.txt
```

4. 重新启动 AstrBot 或在 WebUI 中重载插件

## 依赖库

本插件需要以下 Python 依赖库：
- matplotlib
- pandas
- numpy
- jieba (中文分词)
- wordcloud
- sqlite3 (Python 标准库)

## 配置说明

### SQLite 聊天记录存储插件配置

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

### 群聊统计分析插件配置

插件会自动使用 SQLite 聊天记录存储插件的数据库，无需额外配置。

## 使用方法

### SQLite 聊天记录存储插件命令

#### 1. 查看插件状态

```
/sqlchat_status
```

返回插件当前状态，包括：
- 插件是否启用
- 数据库连接状态
- 数据库路径
- 已存储记录数量

#### 2. 启用插件

```
/sqlchat_enable
```

启用插件并连接到 SQLite 数据库。需要管理员权限。

#### 3. 禁用插件

```
/sqlchat_disable
```

禁用插件并断开数据库连接。需要管理员权限。

#### 4. 修改配置

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

#### 5. 查询聊天记录

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

### 群聊统计分析插件使用

插件会自动监听群聊中的特定关键词，无需额外命令。在群聊中发送以下关键词即可触发相应功能：

#### 1. 生成群聊排名
   
在群聊中发送包含"群聊排名"的消息

```
今天的群聊排名怎么样？
```

机器人将自动回复一张按消息数量排序的条形图。

#### 2. 生成群聊热力图
   
在群聊中发送包含"群聊热力图"的消息

```
请生成今日群聊热力图
```

机器人将自动回复一张展示每个人在不同时段发言数量的热力图。

#### 3. 生成群聊词云
   
在群聊中发送包含"群聊词云"的消息

```
大家今天都聊了什么？群聊词云
```

机器人将自动回复一张基于今日聊天内容的词云图。

## 注意事项

1. SQLite 聊天记录存储插件默认禁用，需要手动启用
2. 所有统计数据仅包含当天（0:00至现在）的聊天记录
3. 热力图最多显示发言数量最多的10位群成员
4. 词云会自动过滤URL、表情符号等内容
5. 统计分析插件需要依赖 SQLite 聊天记录插件的数据，请确保该插件正常工作并已启用
6. SQLite 数据库是单文件数据库，支持并发读取但不支持高并发写入
7. 数据库文件大小无限制，但建议定期备份并清理过旧的数据

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

### SQLite 聊天记录存储插件

1. 如果启用插件时提示错误，请检查数据库路径是否有写入权限
2. 如果插件已启用但没有记录被存储，请检查你使用的是否为 Gewechat 协议
3. 如需进一步调试，可查看 AstrBot 的日志文件

### 群聊统计分析插件

1. 如果关键词没有触发反应，请确认：
   - SQLite 聊天记录插件是否正常工作且已启用
   - 是否在群聊中发送的消息
   - 当天是否有足够的聊天记录
   
2. 如果图表生成失败，检查：
   - 依赖库是否正确安装
   - 对应的中文字体是否存在
