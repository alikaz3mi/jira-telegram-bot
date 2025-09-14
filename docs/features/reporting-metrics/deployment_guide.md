# Deployment Guide

## Overview

This guide covers deploying the Metrics Tracking System in various environments, from development to production. The system can be deployed as a standalone service or integrated into the existing Jira Telegram Bot application.

## Prerequisites

### System Requirements

- **Python**: 3.11 or higher
- **Memory**: Minimum 512MB RAM, Recommended 1GB RAM
- **Storage**: 100MB for application, additional space for logs
- **Network**: HTTPS endpoint accessible from Jira/GitLab servers

### External Dependencies

- **Google Sheets API**: Service account with Sheets access
- **Jira**: Admin access for webhook configuration
- **GitLab**: Project admin access for webhook configuration
- **Redis** (optional): For production caching and idempotency

## Environment Setup

### Development Environment

1. **Clone Repository:**
```bash
git clone https://github.com/your-org/jira-telegram-bot.git
cd jira-telegram-bot
```

2. **Create Virtual Environment:**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows
```

3. **Install Dependencies:**
```bash
pip install -r requirements.txt
pip install -e .
```

4. **Configure Environment:**
```bash
cp prod.env.example .env
# Edit .env with your configuration
```

5. **Setup Configuration:**
```bash
cp config/metrics_config.json.example config/metrics_config.json
# Edit configuration file
```

6. **Run Development Server:**
```bash
python -m jira_telegram_bot.frameworks.fastapi.main
```

### Staging Environment

#### Docker Compose Setup

1. **Create docker-compose.staging.yml:**
```yaml
version: '3.8'

services:
  metrics-api:
    build: .
    ports:
      - "8080:8000"
    environment:
      - LOG_LEVEL=INFO
      - ENVIRONMENT=staging
    env_file:
      - staging.env
    volumes:
      - ./config:/app/config:ro
      - ./logs:/app/logs
    depends_on:
      - redis
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/staging.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - metrics-api
    restart: unless-stopped

volumes:
  redis_data:
```

2. **Create staging.env:**
```bash
# Application
ENVIRONMENT=staging
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000

# Google Sheets
GOOGLE_SERVICE_ACCOUNT_FILE=/app/config/service-account-staging.json
DAILY_SCOREBOARD_SHEET_ID=your_staging_sheet_id
SPRINT_MATRIX_SHEET_ID=your_staging_sheet_id

# Webhook Secrets
JIRA_WEBHOOK_SECRET=staging_jira_secret
GITLAB_WEBHOOK_SECRET=staging_gitlab_secret

# Redis
REDIS_URL=redis://redis:6379/0

# Monitoring
SENTRY_DSN=https://your-staging-sentry-dsn
```

3. **Deploy:**
```bash
docker-compose -f docker-compose.staging.yml up -d
```

### Production Environment

#### Kubernetes Deployment

1. **Create Namespace:**
```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: metrics-tracking
```

2. **Create ConfigMap:**
```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: metrics-config
  namespace: metrics-tracking
data:
  metrics_config.json: |
    {
      "sheets": {
        "daily_scoreboard": {
          "sheet_id": "${DAILY_SCOREBOARD_SHEET_ID}",
          "range_template": "Daily_{month}_{year}!A:G"
        },
        "developer_metrics_matrix": {
          "sheet_id": "${SPRINT_MATRIX_SHEET_ID}",
          "range_template": "Sprint_{sprint_id}!A:P"
        }
      },
      "developers": {
        // Your developer configuration
      },
      "settings": {
        "timezone": "Asia/Tehran",
        "persian_calendar": true,
        "auto_create_sheets": true,
        "retry_attempts": 5,
        "retry_backoff_seconds": 2
      }
    }
```

3. **Create Secret:**
```yaml
# secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: metrics-secrets
  namespace: metrics-tracking
type: Opaque
data:
  google-service-account.json: <base64-encoded-service-account-json>
  jira-webhook-secret: <base64-encoded-secret>
  gitlab-webhook-secret: <base64-encoded-secret>
  sentry-dsn: <base64-encoded-dsn>
```

4. **Create Deployment:**
```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: metrics-api
  namespace: metrics-tracking
spec:
  replicas: 2
  selector:
    matchLabels:
      app: metrics-api
  template:
    metadata:
      labels:
        app: metrics-api
    spec:
      containers:
      - name: metrics-api
        image: your-registry/metrics-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: ENVIRONMENT
          value: "production"
        - name: LOG_LEVEL
          value: "INFO"
        - name: API_HOST
          value: "0.0.0.0"
        - name: API_PORT
          value: "8000"
        - name: GOOGLE_SERVICE_ACCOUNT_FILE
          value: "/app/secrets/google-service-account.json"
        - name: JIRA_WEBHOOK_SECRET
          valueFrom:
            secretKeyRef:
              name: metrics-secrets
              key: jira-webhook-secret
        - name: GITLAB_WEBHOOK_SECRET
          valueFrom:
            secretKeyRef:
              name: metrics-secrets
              key: gitlab-webhook-secret
        - name: REDIS_URL
          value: "redis://redis-service:6379/0"
        - name: SENTRY_DSN
          valueFrom:
            secretKeyRef:
              name: metrics-secrets
              key: sentry-dsn
        volumeMounts:
        - name: config-volume
          mountPath: /app/config
        - name: secrets-volume
          mountPath: /app/secrets
          readOnly: true
        livenessProbe:
          httpGet:
            path: /metrics/health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /metrics/health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
      volumes:
      - name: config-volume
        configMap:
          name: metrics-config
      - name: secrets-volume
        secret:
          secretName: metrics-secrets
```

5. **Create Service:**
```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: metrics-api-service
  namespace: metrics-tracking
spec:
  selector:
    app: metrics-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP
```

6. **Create Ingress:**
```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: metrics-api-ingress
  namespace: metrics-tracking
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rate-limit: "1000"
    nginx.ingress.kubernetes.io/rate-limit-window: "1m"
spec:
  tls:
  - hosts:
    - metrics.your-domain.com
    secretName: metrics-tls
  rules:
  - host: metrics.your-domain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: metrics-api-service
            port:
              number: 80
```

7. **Deploy Redis:**
```yaml
# redis.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: metrics-tracking
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
        volumeMounts:
        - name: redis-data
          mountPath: /data
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "256Mi"
            cpu: "200m"
      volumes:
      - name: redis-data
        persistentVolumeClaim:
          claimName: redis-pvc

---
apiVersion: v1
kind: Service
metadata:
  name: redis-service
  namespace: metrics-tracking
spec:
  selector:
    app: redis
  ports:
  - protocol: TCP
    port: 6379
    targetPort: 6379

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: redis-pvc
  namespace: metrics-tracking
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
```

8. **Apply Kubernetes Resources:**
```bash
kubectl apply -f namespace.yaml
kubectl apply -f secret.yaml
kubectl apply -f configmap.yaml
kubectl apply -f redis.yaml
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f ingress.yaml
```

## CI/CD Pipeline

### GitHub Actions

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy Metrics API

on:
  push:
    branches: [main]
    paths: ['jira_telegram_bot/entities/metrics/**', 'jira_telegram_bot/use_cases/metrics/**', 'jira_telegram_bot/adapters/gateways/google_sheets/**', 'jira_telegram_bot/frameworks/fastapi/webhooks/metrics/**']
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}/metrics-api

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -e .

    - name: Run tests
      run: |
        python -m pytest tests/unit_tests/use_cases/metrics/ -v --cov=jira_telegram_bot.use_cases.metrics
        python -m pytest tests/integration/metrics/ -v

    - name: Run linting
      run: |
        ruff check jira_telegram_bot/entities/metrics/
        ruff check jira_telegram_bot/use_cases/metrics/
        mypy jira_telegram_bot/use_cases/metrics/

  build:
    needs: test
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    outputs:
      image: ${{ steps.meta.outputs.tags }}
      digest: ${{ steps.build.outputs.digest }}

    steps:
    - uses: actions/checkout@v4

    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3

    - name: Log in to Container Registry
      uses: docker/login-action@v3
      with:
        registry: ${{ env.REGISTRY }}
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}

    - name: Extract metadata
      id: meta
      uses: docker/metadata-action@v5
      with:
        images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
        tags: |
          type=ref,event=branch
          type=ref,event=pr
          type=sha,prefix=commit-
          type=raw,value=latest,enable={{is_default_branch}}

    - name: Build and push
      id: build
      uses: docker/build-push-action@v5
      with:
        context: .
        push: true
        tags: ${{ steps.meta.outputs.tags }}
        labels: ${{ steps.meta.outputs.labels }}
        cache-from: type=gha
        cache-to: type=gha,mode=max

  deploy-staging:
    if: github.ref == 'refs/heads/main'
    needs: build
    runs-on: ubuntu-latest
    environment: staging

    steps:
    - uses: actions/checkout@v4

    - name: Configure kubectl
      run: |
        echo "${{ secrets.KUBE_CONFIG_STAGING }}" | base64 -d > /tmp/kubeconfig
        echo "KUBECONFIG=/tmp/kubeconfig" >> $GITHUB_ENV

    - name: Deploy to staging
      run: |
        sed -i "s|IMAGE_TAG|${{ needs.build.outputs.image }}|g" k8s/staging/deployment.yaml
        kubectl apply -f k8s/staging/
        kubectl rollout status deployment/metrics-api -n metrics-tracking-staging

  deploy-production:
    if: github.ref == 'refs/heads/main'
    needs: [build, deploy-staging]
    runs-on: ubuntu-latest
    environment: production

    steps:
    - uses: actions/checkout@v4

    - name: Configure kubectl
      run: |
        echo "${{ secrets.KUBE_CONFIG_PROD }}" | base64 -d > /tmp/kubeconfig
        echo "KUBECONFIG=/tmp/kubeconfig" >> $GITHUB_ENV

    - name: Deploy to production
      run: |
        sed -i "s|IMAGE_TAG|${{ needs.build.outputs.image }}|g" k8s/production/deployment.yaml
        kubectl apply -f k8s/production/
        kubectl rollout status deployment/metrics-api -n metrics-tracking
```

### GitLab CI/CD

Create `.gitlab-ci.yml`:

```yaml
stages:
  - test
  - build
  - deploy-staging
  - deploy-production

variables:
  DOCKER_REGISTRY: $CI_REGISTRY
  IMAGE_NAME: $CI_REGISTRY_IMAGE/metrics-api

test:
  stage: test
  image: python:3.11
  before_script:
    - pip install -r requirements.txt
    - pip install -e .
  script:
    - python -m pytest tests/unit_tests/use_cases/metrics/ -v --cov=jira_telegram_bot.use_cases.metrics
    - python -m pytest tests/integration/metrics/ -v
    - ruff check jira_telegram_bot/entities/metrics/
    - ruff check jira_telegram_bot/use_cases/metrics/
    - mypy jira_telegram_bot/use_cases/metrics/
  coverage: '/TOTAL.+ ([0-9]{1,3}%)/'

build:
  stage: build
  image: docker:latest
  services:
    - docker:dind
  before_script:
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
  script:
    - docker build -t $IMAGE_NAME:$CI_COMMIT_SHA .
    - docker push $IMAGE_NAME:$CI_COMMIT_SHA
    - docker tag $IMAGE_NAME:$CI_COMMIT_SHA $IMAGE_NAME:latest
    - docker push $IMAGE_NAME:latest
  only:
    - main

deploy-staging:
  stage: deploy-staging
  image: kubectl:latest
  before_script:
    - echo "$KUBE_CONFIG_STAGING" | base64 -d > /tmp/kubeconfig
    - export KUBECONFIG=/tmp/kubeconfig
  script:
    - sed -i "s|IMAGE_TAG|$IMAGE_NAME:$CI_COMMIT_SHA|g" k8s/staging/deployment.yaml
    - kubectl apply -f k8s/staging/
    - kubectl rollout status deployment/metrics-api -n metrics-tracking-staging
  environment:
    name: staging
    url: https://metrics-staging.your-domain.com
  only:
    - main

deploy-production:
  stage: deploy-production
  image: kubectl:latest
  before_script:
    - echo "$KUBE_CONFIG_PROD" | base64 -d > /tmp/kubeconfig
    - export KUBECONFIG=/tmp/kubeconfig
  script:
    - sed -i "s|IMAGE_TAG|$IMAGE_NAME:$CI_COMMIT_SHA|g" k8s/production/deployment.yaml
    - kubectl apply -f k8s/production/
    - kubectl rollout status deployment/metrics-api -n metrics-tracking
  environment:
    name: production
    url: https://metrics.your-domain.com
  when: manual
  only:
    - main
```

## Configuration Management

### Environment-Specific Configuration

#### Development (dev.env)
```bash
ENVIRONMENT=development
LOG_LEVEL=DEBUG
API_HOST=localhost
API_PORT=8000
GOOGLE_SERVICE_ACCOUNT_FILE=config/dev-service-account.json
DAILY_SCOREBOARD_SHEET_ID=dev_sheet_id
SPRINT_MATRIX_SHEET_ID=dev_sheet_id
JIRA_WEBHOOK_SECRET=dev_secret
GITLAB_WEBHOOK_SECRET=dev_secret
```

#### Staging (staging.env)
```bash
ENVIRONMENT=staging
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000
GOOGLE_SERVICE_ACCOUNT_FILE=/app/secrets/staging-service-account.json
DAILY_SCOREBOARD_SHEET_ID=staging_sheet_id
SPRINT_MATRIX_SHEET_ID=staging_sheet_id
JIRA_WEBHOOK_SECRET=staging_secret
GITLAB_WEBHOOK_SECRET=staging_secret
REDIS_URL=redis://redis:6379/0
SENTRY_DSN=https://staging-sentry-dsn
```

#### Production (production.env)
```bash
ENVIRONMENT=production
LOG_LEVEL=WARNING
API_HOST=0.0.0.0
API_PORT=8000
GOOGLE_SERVICE_ACCOUNT_FILE=/app/secrets/production-service-account.json
DAILY_SCOREBOARD_SHEET_ID=prod_sheet_id
SPRINT_MATRIX_SHEET_ID=prod_sheet_id
JIRA_WEBHOOK_SECRET=prod_secret
GITLAB_WEBHOOK_SECRET=prod_secret
REDIS_URL=redis://redis-service:6379/0
SENTRY_DSN=https://production-sentry-dsn
PROMETHEUS_ENABLED=true
```

## Monitoring and Observability

### Health Checks

The application provides comprehensive health checks:

```bash
# Basic health check
curl https://metrics.your-domain.com/metrics/health

# Detailed health with dependencies
curl https://metrics.your-domain.com/metrics/health?detailed=true
```

### Prometheus Metrics

Enable Prometheus metrics in production:

```python
# Add to main.py
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI()
Instrumentator().instrument(app).expose(app)
```

Custom metrics to track:

```python
from prometheus_client import Counter, Histogram, Gauge

# Webhook processing metrics
webhook_requests_total = Counter(
    'webhook_requests_total',
    'Total webhook requests',
    ['source', 'event_type', 'status']
)

webhook_processing_duration = Histogram(
    'webhook_processing_duration_seconds',
    'Webhook processing duration',
    ['source', 'event_type']
)

# Sheet operation metrics
sheet_operations_total = Counter(
    'sheet_operations_total',
    'Total sheet operations',
    ['operation', 'sheet', 'status']
)

active_developers = Gauge(
    'active_developers_count',
    'Number of active developers'
)
```

### Grafana Dashboard

Example dashboard configuration:

```json
{
  "dashboard": {
    "title": "Metrics API Dashboard",
    "panels": [
      {
        "title": "Webhook Requests/sec",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(webhook_requests_total[5m])",
            "legendFormat": "{{source}} - {{event_type}}"
          }
        ]
      },
      {
        "title": "Processing Duration",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, webhook_processing_duration_seconds_bucket)",
            "legendFormat": "95th percentile"
          }
        ]
      },
      {
        "title": "Error Rate",
        "type": "stat",
        "targets": [
          {
            "expr": "rate(webhook_requests_total{status!='success'}[5m]) / rate(webhook_requests_total[5m])",
            "legendFormat": "Error Rate"
          }
        ]
      }
    ]
  }
}
```

### Logging Configuration

Structured logging configuration:

```python
# logging_config.py
import logging
import logging.config

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        },
        'json': {
            'format': '{"timestamp": "%(asctime)s", "logger": "%(name)s", "level": "%(levelname)s", "message": "%(message)s", "module": "%(module)s", "funcName": "%(funcName)s"}'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json' if os.getenv('ENVIRONMENT') == 'production' else 'default',
            'level': 'INFO'
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/metrics.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'json',
            'level': 'INFO'
        }
    },
    'loggers': {
        'jira_telegram_bot.use_cases.metrics': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False
        },
        'jira_telegram_bot.adapters.gateways.google_sheets': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False
        }
    }
}

logging.config.dictConfig(LOGGING_CONFIG)
```

## Security Considerations

### Webhook Security

1. **Use HTTPS**: Always use HTTPS endpoints for webhooks
2. **Verify Signatures**: Implement webhook signature verification
3. **Rate Limiting**: Implement proper rate limiting
4. **Input Validation**: Validate all incoming webhook payloads

### Secret Management

1. **Environment Variables**: Use environment variables for secrets
2. **Secret Stores**: Use Kubernetes secrets or HashiCorp Vault
3. **Rotation**: Implement regular secret rotation
4. **Access Control**: Limit access to service accounts and credentials

### Network Security

1. **Firewall Rules**: Restrict access to webhook endpoints
2. **VPC**: Deploy in private VPC with controlled access
3. **Load Balancer**: Use load balancer for SSL termination
4. **IP Whitelisting**: Whitelist Jira/GitLab server IPs if possible

## Backup and Recovery

### Data Backup

1. **Google Sheets**: Sheets are automatically backed up by Google
2. **Configuration**: Backup configuration files regularly
3. **Redis Data**: Backup Redis data for idempotency cache
4. **Application Logs**: Archive logs for audit and debugging

### Recovery Procedures

1. **Application Recovery**: Redeploy from source control
2. **Configuration Recovery**: Restore from backup configuration
3. **Sheet Recovery**: Google Sheets have version history
4. **Cache Recovery**: Redis data can be rebuilt from webhook replay

### Disaster Recovery

1. **Multi-Region Deployment**: Deploy in multiple regions
2. **Database Replication**: Replicate critical data
3. **Webhook Replay**: Implement webhook event replay capability
4. **Automated Failover**: Implement automated failover procedures

## Performance Tuning

### Application Optimization

1. **Async Processing**: Use async/await for I/O operations
2. **Connection Pooling**: Pool Google API connections
3. **Batch Operations**: Batch sheet updates when possible
4. **Caching**: Cache configuration and sheet metadata

### Infrastructure Optimization

1. **Resource Allocation**: Right-size containers
2. **Auto-scaling**: Implement horizontal pod autoscaling
3. **Load Balancing**: Distribute load across instances
4. **CDN**: Use CDN for static assets if any

### Monitoring Performance

1. **Response Times**: Monitor API response times
2. **Throughput**: Track requests per second
3. **Resource Usage**: Monitor CPU and memory usage
4. **Error Rates**: Track error rates and types

This deployment guide provides comprehensive coverage for deploying the Metrics Tracking System in various environments with proper monitoring, security, and operational procedures.
