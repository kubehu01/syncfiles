FROM python:3.11-slim

WORKDIR /app

# 先复制 requirements.txt，利用 Docker 缓存
COPY requirements.txt .
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn && \
    pip install --no-cache-dir -r requirements.txt

# 再复制代码和启动脚本
COPY . .
COPY --chmod=755 docker-entrypoint.sh /app/
# RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 3000

# 使用 entrypoint + cmd 组合
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "app.py"]

