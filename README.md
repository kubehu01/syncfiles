# 企业微信 Docker 镜像同步工具（Python版）

通过企业微信消息触发 Docker 镜像同步到阿里云仓库的自动化工具。

## ✨ 功能特点

- 🚀 **企业微信消息触发** - 通过企业微信发送消息即可触发同步
- 🔐 **消息加密支持** - 支持企业微信消息 AES 加密/解密
- 📦 **镜像同步** - 自动同步 Docker 镜像到阿里云容器镜像服务
- ⚡ **并发处理** - GitHub Actions 并行处理多个镜像
- 📥 **文件上传** - 支持 URL 文件下载并上传到青云对象存储
- 🌐 **代理支持** - 智能代理配置，自动检测可用性
- 📝 **任务管理** - 文件锁机制，防止并发冲突
- 🐳 **Docker 部署** - 开箱即用的 Docker 化部署方案

## 🛠️ 技术栈

- **后端**: Python 3.11 + Flask
- **消息处理**: 企业微信 API + PyCrypto 加解密
- **镜像同步**: GitHub Actions + Docker
- **对象存储**: 青云 QingStor SDK
- **并发控制**: 文件锁 + 任务状态管理

## 快速开始

### 1. 克隆项目

```bash
git clone <your-repo>
cd syncfiles
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp env.example .env
```

编辑 `.env` 文件：

```env
# 企业微信配置
CORP_ID=your_corp_id
AGENT_ID=your_agent_id
SECRET=your_secret
TOKEN=your_token
ENCODING_AES_KEY=your_encoding_aes_key

# GitHub 配置
GITHUB_TOKEN=your_github_token
GITHUB_REPO=owner/repo
GITHUB_BRANCH=main

# 阿里云配置（GitHub Secrets）
DOCKER_REGISTRY=registry.cn-hangzhou.aliyuncs.com
DOCKER_NAMESPACE=your_namespace

# 服务配置
PORT=3000
```

### 4. 运行服务

```bash
python app.py
```

或使用 Docker：

```bash
docker-compose up -d
```

## 使用方法

在企业微信中发送消息到配置的应用：

```
nginx:latest
```

或发送多个镜像（用逗号或换行分隔）：

```
nginx, redis, mysql
```

系统会自动：
1. 解析镜像列表
2. 更新 GitHub 仓库的 `images.txt`
3. 触发 GitHub Actions 同步任务
4. 推送消息反馈结果

## 项目结构

```
.
├── app.py                      # Flask 主应用
├── wechat/                     # 企业微信模块
│   ├── __init__.py
│   ├── crypto.py              # 消息加解密（AES）
│   └── api.py                 # 企业微信 API 客户端
├── github_api/                 # GitHub API 模块
│   ├── __init__.py
│   └── api.py                 # GitHub API 客户端
├── qingstor_api/               # 青云对象存储模块
│   ├── __init__.py
│   └── client.py              # 对象存储客户端
├── utils/                      # 工具模块
│   ├── __init__.py
│   ├── locks.py               # 文件锁管理
│   └── proxy.py               # 代理管理
├── .github/workflows/          # GitHub Actions
│   └── docker-image-sync.yml  # 镜像同步工作流
├── requirements.txt            # Python 依赖
├── Dockerfile                  # Docker 配置
├── docker-compose.yml         # Docker Compose
├── docker-entrypoint.sh       # 启动脚本
├── images.txt                  # 镜像列表文件
├── env.example                 # 环境变量模板
└── README.md                   # 本文档

```

## 详细配置

### 1. 企业微信配置

**步骤：**

1. 登录 [企业微信管理后台](https://work.weixin.qq.com/)
2. 进入 **应用管理** → 创建企业应用
3. 填写应用信息：
   - 应用名称：Docker 镜像同步
   - 应用介绍：Docker 镜像同步工具
4. 获取以下信息：
   - **CORP_ID**：企业 ID（在「我的企业」页面查看）
   - **AGENT_ID**：应用 ID
   - **SECRET**：应用密钥（Secret）
5. 配置回调（参考 [回调接口文档](https://developer.work.weixin.qq.com/document/path/90930)）：
   - 回调 URL：`http://your-server:3000/wechat/callback`
   - 设置 Token（自己生成，任意字符串）
   - 设置 EncodingAESKey（企业微信自动生成，43 字节）

**配置示例：**

```env
CORP_ID=wwxxxxxxxxxxxxxxxx
AGENT_ID=1000001
SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TOKEN=your_random_token
ENCODING_AES_KEY=your_43_chars_encoding_aes_key

# 说明：
# - TOKEN: 任意设置的字符串，回调 URL 验证时需要
# - ENCODING_AES_KEY: 企业微信自动生成的 43 字节字符串
```

**注意事项：**

- 回调模式建议使用**加密模式**（EncodingAESKey）
- 确保回调 URL 可以从外网访问
- Token 和 ENCODING_AES_KEY 必须与后台配置一致

### 2. 青云对象存储配置（可选）

**步骤：**

1. 登录 [青云管理控制台](https://console.qingcloud.com/)
2. 进入 **对象存储** → **访问密钥**
3. 创建或查看现有的 Access Key
4. 获取：
   - **QINGSTOR_ACCESS_KEY_ID**：访问密钥 ID
   - **QINGSTOR_SECRET_ACCESS_KEY**：访问密钥 Secret
5. 确定区域（Zone），例如：`pek3a`（北京3区A）

**配置示例：**

```env
QINGSTOR_ACCESS_KEY_ID=your_access_key_id
QINGSTOR_SECRET_ACCESS_KEY=your_secret_access_key
QINGSTOR_ZONE=pek3a
```

**注意事项：**
- 确保在青云控制台中创建了名为 `tmp` 的存储桶（bucket）
- 如果没有 `tmp` bucket，需要在控制台中手动创建
- 此功能为可选功能，未配置时不会启用
- **青云对象存储使用直连，不走代理**

### 4. 代理配置（可选）

如果服务器无法直接访问某些网站（如 GitHub、Docker Hub），可以配置代理：

**配置项：**

```env
# 代理 URL（HTTP 或 SOCKS5）
PROXY_URL=http://proxy.example.com:8080

# 不使用代理的域名列表（逗号分隔）
# 青云对象存储默认不走代理
NO_PROXY_DOMAINS=localhost,127.0.0.1,qingstor.com
```

**特性：**
- ✅ 启动时自动检测代理可用性（访问 Google 测试）
- ✅ 代理不可用时自动降级为直连模式
- ✅ 支持域名白名单
- ✅ 青云对象存储强制直连（不走代理）

**启动日志示例：**
```
🌐 检测到代理配置: http://proxy.example.com:8080
  直连域名: localhost, 127.0.0.1, qingstor.com
✅ 代理可用: http://proxy.example.com:8080
🔗 GitHub API 使用代理
```

**代理不可用时的日志：**
```
🌐 检测到代理配置: http://proxy.example.com:8080
⚠️  代理连接失败: http://proxy.example.com:8080
   将使用非代理模式继续运行
```

### 5. GitHub 配置

#### 5.1 获取 GitHub Token

**步骤：**

1. 访问 [GitHub Settings](https://github.com/settings/tokens)
2. 点击 **Developer settings** → **Personal access tokens** → **Tokens (classic)**
3. 点击 **Generate new token (classic)**
4. 填写 Token 信息：
   - Note: `image-sync-token`
   - Expiration: `90 days`（或按需设置）
5. 勾选权限：
   - ✅ **repo** - 完整仓库权限
   - ✅ **workflow** - 工作流权限
6. 点击 **Generate token**，复制 Token

**配置到 .env：**

```env
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GITHUB_REPO=your_username/your_repo
GITHUB_BRANCH=main
```

#### 5.2 配置 GitHub Secrets

**添加以下 Secrets：**

| Secret 名称        | 说明            | 示例值                               |
| ---------------- | ------------- | --------------------------------- |
| DOCKER_USERNAME  | 阿里云容器镜像服务用户名 | `your-username`                   |
| DOCKER_PASSWORD  | 阿里云密码或访问令牌    | `your-password`                   |
| DOCKER_REGISTRY  | 阿里云仓库地址       | `registry.cn-hangzhou.aliyuncs.com` |
| DOCKER_NAMESPACE | 阿里云命名空间      | `your-namespace`                  |

**获取阿里云凭据：**

1. 登录 [阿里云容器镜像服务](https://cr.console.aliyun.com/)
2. 点击 **访问凭证** → **设置固定密码**
3. 复制用户名和密码
4. 分别填入 GitHub Secrets

## 部署方式

### 方式一：使用 Docker Compose（推荐）

```bash
# 1. 克隆项目
git clone <your-repo>
cd syncfiles

# 2. 配置环境变量
cp env.example .env
# 编辑 .env 文件，填写配置

# 3. 启动服务
docker-compose up -d

# 4. 查看日志
docker-compose logs -f image-sync

# 5. 停止服务
docker-compose down
```

### 方式二：直接运行 Python

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp env.example .env
# 编辑 .env 文件

# 3. 运行服务
python app.py

# 服务将在 http://localhost:3000 启动
```

## 使用说明

系统自动识别两种不同类型的请求：

### 功能区分规则

| 输入类型 | 识别规则 | 处理方式 |
|---------|---------|---------|
| **HTTPS 链接** | 以 `https://` 或 `http://` 开头 | 下载文件并上传到青云对象存储 |
| **Docker 镜像** | 包含 `:`（标签）或 `/`（仓库） | 同步到阿里云容器镜像服务 |
| **其他内容** | 无匹配 | 返回帮助信息 |

### 使用示例

### 1. Docker 镜像同步

**单个镜像：**

```
nginx:latest
```

**多个镜像（逗号分隔）：**

```
nginx:latest, redis:7.0, mysql:8.0
```

**多个镜像（换行）：**

```
nginx:latest
redis:7.0
mysql:8.0
```

**指定平台架构：**

```
--platform=linux/amd64 nginx:latest
```

**系统自动识别**并同步到阿里云：

```
registry.cn-hangzhou.aliyuncs.com/your-namespace/nginx:latest
```

### 2. 文件下载上传（青云对象存储）

当消息是 HTTPS 链接时，系统会自动下载文件并上传到青云对象存储：

```
https://example.com/file.pdf
https://github.com/example/repo/archive/master.zip
```

**系统会自动：**
1. 下载文件
2. 上传到青云对象存储的 `tmp` bucket
3. 返回文件的访问链接

**响应消息：**
```
✅ 文件上传成功！

文件名: file.pdf
文件大小: 102400 字节
存储桶: tmp
下载链接: https://tmp.pek3a.qingstor.com/uuid.pdf
```

### 消息反馈

系统会自动发送 2 条消息：

1. **收到请求时**：确认镜像列表
```
🔄 正在处理镜像同步请求...
共 3 个镜像：
1. nginx:latest → registry.cn-hangzhou.aliyuncs.com/namespace/nginx:latest
2. redis:7.0 → registry.cn-hangzhou.aliyuncs.com/namespace/redis:7.0
3. mysql:8.0 → registry.cn-hangzhou.aliyuncs.com/namespace/mysql:8.0
```

2. **完成后**：返回执行结果
   - ✅ 成功：显示同步成功的镜像数量
   - ❌ 失败：显示失败的镜像列表和错误原因

## 故障排查

### 回调验证失败

**症状**：企业微信后台提示"回调验证失败"

**解决方案**：

1. 检查 `.env` 中的 `TOKEN` 是否与企业微信后台配置一致
2. 确保选择了"安全模式"或"加密模式"
3. 查看服务器日志：
   ```bash
   docker-compose logs -f
   ```
4. 验证回调 URL 是否可访问

### 镜像同步失败

**症状**：GitHub Actions 执行失败

**检查项**：

1. GitHub Secrets 配置是否正确
   - `DOCKER_USERNAME`
   - `DOCKER_PASSWORD`
   - `DOCKER_REGISTRY`
   - `DOCKER_NAMESPACE`
2. 镜像名称是否正确（不存在或网络问题）
3. 查看 GitHub Actions 日志
   ```
   https://github.com/owner/repo/actions
   ```

### 任务冲突

**症状**：提示"已有任务正在处理中"

**说明**：系统同一时间只处理一个任务，请等待当前任务完成后再试

**解决**：
- 等待 5-10 分钟后再发送新请求
- 查看当前任务的 GitHub Actions 运行状态

### 服务健康检查

```bash
# 检查服务状态
curl http://localhost:3000/health

# 查看日志
docker-compose logs -f image-sync

# 查看容器状态
docker-compose ps
```

## 常见问题

**Q: 支持哪些镜像源？**  
A: 支持所有公共 Docker 仓库（Docker Hub、GCR、K8s 等）

**Q: 如何查看同步历史？**  
A: 查看 GitHub Actions 运行历史或仓库的 `images.txt` 提交记录

**Q: 失败会重试吗？**  
A: 不会自动重试，需要手动重新发送镜像名称

**Q: 可以同步私有仓库镜像吗？**  
A: 需要在 GitHub Actions 中配置相应的认证信息

**Q: 如何修改同步的目标仓库？**  
A: 修改 `.env` 中的 `DOCKER_REGISTRY` 和 `DOCKER_NAMESPACE`

## 高级配置

### 内网穿透（FRP）

如果服务器在内网，需要使用 FRP 进行内网穿透：

```bash
# FRP 服务端配置（公网服务器）
# frps.ini
[common]
bind_port = 7000
```

```bash
# FRP 客户端配置（内网服务器）
# frpc.ini
[common]
server_addr = your-frps-ip
server_port = 7000

[web]
type = tcp
local_ip = 127.0.0.1
local_port = 3000
remote_port = 30000
```

企业微信回调 URL: `http://your-frps-ip:30000/wechat/callback`

### 定时任务

系统会在每天凌晨 00:00:00 自动：
1. 将当前的 `images.txt` 内容上传到 GitHub
2. 重置本地的 `images.txt` 为空

这确保每天有一个干净的同步列表。

## API 限制

- **企业微信**：每分钟最多 600 次
- **GitHub API**：根据账号级别有不同限制
- **任务处理**：同一时间只处理一个同步任务
- **超时时间**：GitHub Actions 最多等待 5 分钟

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT

