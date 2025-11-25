# RecLicense Kubernetes 部署指南

本目录包含在 Kubernetes 集群上部署 RecLicense 的配置文件。

## 前置要求

- Kubernetes 集群 v1.26+
- kubectl 命令行工具
- 已安装 metrics-server（用于自动扩缩容）
- 存储类（StorageClass）支持动态PV分配

## 架构说明

RecLicense 由以下组件组成：

1. **MongoDB** - 数据库，存储许可证分析数据
2. **Backend** - Flask API 服务器，处理许可证检测和兼容性分析
3. **Frontend** - Caddy web 服务器，提供用户界面

## 镜像构建

### Backend 镜像

```bash
cd /path/to/RecLicense
docker build -f deploy/backend.dockerfile -t reclicense-backend:v1.5 .
```

**重要修改（已包含在此分支）：**
- 添加了缺失的 Python 依赖：`lxml`, `pandas`, `numpy`
- 修复了日志目录问题：创建 `/backend/app/logging` 目录
- 基础镜像从 `python:3.8-slim-buster` 更新为 `python:3.8-slim-bullseye`

### Frontend 镜像

```bash
cd /path/to/RecLicense
docker build -f deploy/frontend.dockerfile -t reclicense-frontend:v1.1 .
```

**重要修改（已包含在此分支）：**
- Caddyfile 配置：使用 `:80` 替代环境变量 `{$RECLIC_DOMAIN}`
- Backend 服务名称：使用 Kubernetes 服务名 `reclicense-backend:5000`

## 镜像分发到所有节点

由于使用 `imagePullPolicy: Never`，需要将镜像分发到所有 worker 节点：

```bash
# 导出镜像
docker save reclicense-backend:v1.5 > reclicense-backend-v1.5.tar
docker save reclicense-frontend:v1.1 > reclicense-frontend-v1.1.tar

# 在每个 worker 节点上导入
# 方法1: 使用 ctr (containerd)
sudo ctr -n k8s.io images import reclicense-backend-v1.5.tar
sudo ctr -n k8s.io images import reclicense-frontend-v1.1.tar

# 方法2: 使用 docker (如果节点安装了 docker)
docker load < reclicense-backend-v1.5.tar
docker load < reclicense-frontend-v1.1.tar
```

## 部署步骤

### 1. 创建命名空间和基础资源

```bash
kubectl apply -f k8s/deployment.yaml
```

这将创建：
- `reclicense` 命名空间
- Secret（GitHub Token 和其他配置）
- PersistentVolumeClaim（MongoDB 和 Backend 文件存储）
- Deployments（MongoDB, Backend, Frontend）
- Services（ClusterIP 和 NodePort）

### 2. 配置 GitHub Token（可选）

如果需要 GitHub API 功能，编辑 Secret：

```bash
kubectl edit secret reclicense-config -n reclicense
```

修改 `GITHUB_TOKEN` 字段。

### 3. 验证部署

```bash
# 查看所有资源
kubectl get all -n reclicense

# 查看 pod 状态和分布
kubectl get pods -n reclicense -o wide

# 查看日志
kubectl logs -n reclicense -l app=reclicense-backend
kubectl logs -n reclicense -l app=reclicense-frontend
```

### 4. 配置自动扩缩容（可选）

```bash
kubectl apply -f k8s/hpa.yaml
```

HPA 配置：

**Frontend:**
- 最小副本: 2
- 最大副本: 8
- 扩容阈值: CPU > 70% 或 Memory > 80%

**Backend:**
- 最小副本: 1
- 最大副本: 6
- 扩容阈值: CPU > 60% 或 Memory > 75%

查看 HPA 状态：

```bash
kubectl get hpa -n reclicense
kubectl describe hpa -n reclicense
```

## 访问应用

Frontend 通过 NodePort 暴露在端口 **30600**：

```
http://<任意节点IP>:30600
```

例如：
- http://10.100.6.211:30600
- http://10.100.6.212:30600
- http://10.100.6.213:30600
- http://10.100.6.214:30600

## 资源配置

### Backend

- CPU 请求: 1 core
- CPU 限制: 4 cores
- 内存请求: 2Gi
- 内存限制: 6Gi

### Frontend

- CPU 请求: 200m
- CPU 限制: 1 core
- 内存请求: 256Mi
- 内存限制: 2Gi

### MongoDB

- CPU 请求: 1 core
- CPU 限制: 4 cores
- 内存请求: 2Gi
- 内存限制: 10Gi
- 存储: 50Gi PVC

## 节点调度

所有应用组件配置了 `nodeSelector` 只运行在 worker 节点：

```yaml
nodeSelector:
  node-role.kubernetes.io/worker: ""
```

这确保应用不会调度到 master 节点。

## 故障排除

### Pod 一直处于 Pending 状态

检查 PVC 是否成功绑定：

```bash
kubectl get pvc -n reclicense
```

### Backend Pod 崩溃

查看日志：

```bash
kubectl logs -n reclicense -l app=reclicense-backend --tail=100
```

常见问题：
- 缺失 Python 依赖 → 已在 v1.5 修复
- 日志目录不存在 → 已在 v1.5 修复

### Frontend Pod 崩溃

查看日志：

```bash
kubectl logs -n reclicense -l app=reclicense-frontend --tail=50
```

常见问题：
- Caddy 配置错误 → 已在 v1.1 修复（使用 `:80` 代替域名变量）

### 镜像拉取失败

确保镜像已导入到 pod 调度的节点：

```bash
# 在目标节点上检查
sudo ctr -n k8s.io images ls | grep reclicense
```

### HPA 不工作

检查 metrics-server：

```bash
kubectl get deployment metrics-server -n kube-system
kubectl top pods -n reclicense
```

## 清理部署

```bash
# 删除 HPA
kubectl delete -f k8s/hpa.yaml

# 删除所有资源
kubectl delete -f k8s/deployment.yaml

# 删除命名空间（包括所有资源）
kubectl delete namespace reclicense
```

## 版本历史

### v1.5 (Backend)
- 添加缺失的 Python 依赖：lxml, pandas, numpy
- 修复日志目录创建问题
- 更新基础镜像到 Debian Bullseye

### v1.1 (Frontend)
- 修复 Caddyfile 配置（使用 :80 端口监听）
- 更新 backend 代理地址为 Kubernetes 服务名

## 技术支持

如有问题，请查看：
1. Pod 日志：`kubectl logs -n reclicense <pod-name>`
2. Pod 事件：`kubectl describe pod -n reclicense <pod-name>`
3. HPA 状态：`kubectl describe hpa -n reclicense`
