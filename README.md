# AstrBot Gewechat 聊天记录 Elasticsearch 存储插件

一个用于将 Gewechat 微信协议的聊天记录保存到 Elasticsearch 的 AstrBot 插件。

## 功能介绍

本插件可以自动捕获 Gewechat 协议中的微信消息，并将其存储到 Elasticsearch 中，方便后续查询和分析。主要存储以下信息：

- 群聊 ID（如果有）
- 发送人 ID
- 发送人名称
- 消息内容
- 消息时间
- 消息 ID
- 平台类型

## Elasticsearch 索引结构

本插件在 Elasticsearch 中创建的索引结构如下：

```json
{
  "mappings": {
    "properties": {
      "group_id": {
        "type": "keyword"
      },
      "sender_id": {
        "type": "keyword"
      },
      "sender_name": {
        "type": "text",
        "fields": {
          "keyword": {
            "type": "keyword"
          }
        }
      },
      "message": {
        "type": "text",
        "analyzer": "ik_max_word"
      },
      "timestamp": {
        "type": "date"
      },
      "message_id": {
        "type": "keyword"
      },
      "platform": {
        "type": "keyword"
      }
    }
  }
}
```

说明：
- `group_id`: 群聊ID，使用 keyword 类型便于精确查询
- `sender_id`: 发送者ID，使用 keyword 类型便于精确查询
- `sender_name`: 发送者名称，使用 text 类型支持全文检索，并增加 keyword 子字段便于聚合和排序
- `message`: 消息内容，使用 text 类型并配合 ik_max_word 分词器（如果已安装）以支持中文分词
- `timestamp`: 消息时间戳，使用 date 类型便于日期范围查询
- `message_id`: 消息ID，使用 keyword 类型便于精确查询
- `platform`: 平台类型，使用 keyword 类型便于精确查询

## 安装步骤

1. 确保已安装 AstrBot 并正确配置 Gewechat
2. 将本插件克隆到 AstrBot 的插件目录中：

```bash
cd <AstrBot安装目录>/data/plugins/
git clone https://github.com/lihongjie224/astr-bot-sync
```

3. 安装插件依赖：

```bash
cd astr-bot-sync
pip install -r requirements.txt
```

4. 重新启动 AstrBot 或在 WebUI 中重载插件

## 配置说明

插件首次加载时会自动创建默认配置文件 `es_chat_store_config.json`，内容如下：

```json
{
  "es_host": "http://localhost:9200",
  "es_index": "gewechat_chat_records",
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
/eschat_status
```

返回插件当前状态，包括：
- 插件是否启用
- Elasticsearch 连接状态
- 索引是否存在
- 已存储记录数量

### 2. 启用插件

```
/eschat_enable
```

启用插件并连接到 Elasticsearch。需要管理员权限。

### 3. 禁用插件

```
/eschat_disable
```

禁用插件并断开 Elasticsearch 连接。需要管理员权限。

### 4. 修改配置

```
/eschat_config [参数名] [参数值]
```

可配置的参数：
- `es_host`: Elasticsearch 服务器地址，例如 `http://localhost:9200`
- `es_index`: 存储记录的索引名称，例如 `gewechat_chat_records`

示例：
```
/eschat_config es_host http://192.168.1.100:9200
/eschat_config es_index my_chat_records
```

注意：修改配置后需要重载插件才能生效。

## 注意事项

1. 请确保 Elasticsearch 服务器已正确安装并运行
2. 建议使用 Elasticsearch 7.x 或更高版本
3. 如需中文分词支持，请在 Elasticsearch 中安装 IK 分词器插件
4. 本插件默认禁用，需要手动启用
5. 插件会自动创建索引，无需手动创建

## 数据查询示例

安装完成后，可以使用 Elasticsearch 的查询语法查询存储的聊天记录，例如：

### 基本查询示例（Kibana Dev Tools）

```
# 查询所有记录
GET gewechat_chat_records/_search

# 查询特定群聊的消息
GET gewechat_chat_records/_search
{
  "query": {
    "term": {
      "group_id": "12345678@chatroom"
    }
  }
}

# 查询特定用户的消息
GET gewechat_chat_records/_search
{
  "query": {
    "term": {
      "sender_id": "wxid_abcdefg"
    }
  }
}

# 全文搜索消息内容
GET gewechat_chat_records/_search
{
  "query": {
    "match": {
      "message": "搜索关键词"
    }
  }
}

# 按时间范围查询
GET gewechat_chat_records/_search
{
  "query": {
    "range": {
      "timestamp": {
        "gte": "2025-04-01",
        "lte": "2025-04-13"
      }
    }
  }
}
```

## 故障排除

1. 如果启用插件时提示连接失败，请检查 Elasticsearch 服务是否正常运行，以及配置的 `es_host` 是否正确
2. 如果插件已启用但没有记录被存储，请检查你使用的是否为 Gewechat 协议
3. 如需进一步调试，可查看 AstrBot 的日志文件
