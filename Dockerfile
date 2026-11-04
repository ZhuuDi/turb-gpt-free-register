# turb-gpt 运行时镜像
# 代码不打进镜像:compose 把部署目录 bind-mount 到 /app,
# 本镜像只提供 Python 3.12 + Node 18 运行时和 pip 依赖。
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

# nodejs: sentinel PoW runner 需要 Node 18+(bookworm 源自带 18.x,纯标准库,无需 npm install)
# curl: healthcheck 备用
RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs tzdata curl \
    && ln -fs /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && rm -rf /var/lib/apt/lists/*

# 依赖层单独缓存:requirements.txt 不变时,重新 build 只需秒级
COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt

WORKDIR /app
EXPOSE 5000

CMD ["python", "web.py", "--host", "0.0.0.0", "--port", "5000"]
