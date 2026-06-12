# Kubernetes DevOps Junior Project

A production-grade Todo API deployed on a local Kubernetes cluster using k3d, with PostgreSQL as the database, Helm for package management, and a full observability stack with Prometheus and Grafana.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Kubernetes Concepts](#kubernetes-concepts)
- [Helm Chart](#helm-chart)
- [Monitoring](#monitoring)
- [Security Decisions](#security-decisions)
- [Why These Technologies](#why-these-technologies)

---

## Overview

This project simulates a real-world Kubernetes deployment workflow. Beyond running an API, it demonstrates how a DevOps engineer handles:

- Containerizing an application securely
- Deploying and managing workloads in Kubernetes
- Handling startup dependencies between services
- Packaging infrastructure as a reusable Helm chart
- Instrumenting an application for Prometheus observability
- Visualizing metrics in Grafana

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Local Cluster — k3d (k3s inside Docker)                    │
│                                                             │
│  namespace: todo-helm                                       │
│    ├── Deployment: todo-app (3 replicas)                    │
│    │     ├── InitContainer: waits for PostgreSQL            │
│    │     ├── StartupProbe:  allows slow startup             │
│    │     ├── ReadinessProbe: controls traffic routing       │
│    │     └── LivenessProbe: triggers self-healing           │
│    ├── StatefulSet: postgres (persistent storage)           │
│    ├── Service: internal load balancer                      │
│    ├── Ingress: external access via todo.localhost          │
│    ├── ConfigMap: non-sensitive configuration               │
│    └── Secret: database password (base64)                   │
│                                                             │
│  namespace: monitoring                                      │
│    ├── Prometheus: scrapes /metrics every 15s               │
│    ├── Grafana: dashboards and PromQL queries               │
│    ├── Alertmanager: alert routing                          │
│    ├── Node Exporter: CPU/RAM per node                      │
│    └── kube-state-metrics: pod/deployment state            │
└─────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| API | FastAPI | REST API with automatic OpenAPI docs |
| Database | PostgreSQL 16 | Relational database in a StatefulSet |
| ORM | SQLAlchemy | Database access layer |
| Container | Docker | Application packaging |
| Orchestration | Kubernetes (k3s) | Container scheduling and management |
| Local Cluster | k3d | k3s running inside Docker for local dev |
| Package Manager | Helm | Kubernetes application packaging |
| Metrics | prometheus-fastapi-instrumentator | Exposes /metrics endpoint |
| Monitoring | Prometheus + Grafana | Metrics collection and visualization |
| Alerts | Alertmanager | Alert routing |

---

## Project Structure

```
.
├── app/
│   ├── main.py           # FastAPI app with /metrics endpoint
│   ├── models.py         # Pydantic schemas
│   ├── database.py       # SQLAlchemy + PostgreSQL connection
│   ├── requirements.txt  # Python dependencies
│   └── Dockerfile        # Multi-stage, non-root container
├── k8s/                  # Raw Kubernetes manifests
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── postgres-statefulset.yaml
│   ├── postgres-service.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   └── ingress.yaml
├── helm/
│   └── todo-app/         # Helm chart
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
│           ├── deployment.yaml
│           ├── postgres.yaml
│           ├── service.yaml
│           ├── secret.yaml
│           └── ingress.yaml
└── monitoring/
    ├── prometheus-values.yaml   # kube-prometheus-stack config
    └── servicemonitor.yaml      # Tells Prometheus where to scrape
```

---

## Getting Started

### Prerequisites

- Docker
- k3d: `curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash`
- kubectl: `curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" && sudo mv kubectl /usr/local/bin/`
- Helm: `curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash`

### Cluster Setup

```bash
# Create cluster with load balancer on port 8080
k3d cluster create todo-cluster --port "8080:80@loadbalancer" --agents 2

# Build and import the Docker image
docker build -t todo-app:latest -f app/Dockerfile .
k3d image import todo-app:latest -c todo-cluster
```

### Deploy with Helm

```bash
# Create namespace and deploy
kubectl create namespace todo-helm
helm install todo-release ./helm/todo-app -n todo-helm

# Verify pods are running
kubectl get pods -n todo-helm
```

### Access the API

```bash
kubectl port-forward service/todo-release-service 9000:80 -n todo-helm
curl http://localhost:9000/
curl http://localhost:9000/metrics
```

### Deploy Monitoring

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
kubectl create namespace monitoring
helm upgrade --install kube-prometheus prometheus-community/kube-prometheus-stack \
  -n monitoring -f monitoring/prometheus-values.yaml
kubectl apply -f monitoring/servicemonitor.yaml
```

### Access Grafana

```bash
kubectl port-forward svc/kube-prometheus-grafana 3000:80 -n monitoring
```

Open `http://localhost:3000` — user: `admin`, password: `admin123`

---

## Kubernetes Concepts

### Why InitContainer?
PostgreSQL takes a few seconds to be ready after its pod starts. Without an initContainer, the app pod would crash trying to connect. The initContainer runs `pg_isready` in a loop until PostgreSQL accepts connections, only then allowing the app container to start.

```
initContainer: pg_isready → loop until ready → exit 0
                                                     ↓
                                            app container starts
```

### Why Three Probes?

| Probe | Purpose | Behavior on failure |
|-------|---------|-------------------|
| startupProbe | Allows slow startup (up to 100s) | Delays liveness/readiness |
| readinessProbe | Is the app ready for traffic? | Removed from load balancer |
| livenessProbe | Is the app still alive? | Pod is restarted |

### StatefulSet vs Deployment

PostgreSQL uses a StatefulSet because it needs:
- A stable network identity (`postgres-0`, not a random hash)
- Persistent storage that survives pod restarts (PersistentVolumeClaim)
- Ordered startup and shutdown

The app uses a Deployment because it is stateless — any replica can handle any request.

---

## Helm Chart

The Helm chart in `helm/todo-app/` parameterizes all Kubernetes manifests. Values in `values.yaml` can be overridden at install time:

```bash
# Deploy with 1 replica (dev)
helm install todo-dev ./helm/todo-app -n dev --set replicaCount=1

# Deploy with 5 replicas (prod)
helm install todo-prod ./helm/todo-app -n prod --set replicaCount=5

# View release history
helm history todo-release -n todo-helm

# Rollback to previous version
helm rollback todo-release 2 -n todo-helm
```

---

## Monitoring

### Metrics Flow

```
FastAPI /metrics endpoint
        ↓ (every 15s)
Prometheus scrapes via ServiceMonitor
        ↓
Grafana queries via PromQL
```

### Useful PromQL Queries

```promql
# Request rate per second
rate(http_requests_total[1m])

# Average latency
rate(http_request_duration_seconds_sum[1m]) / rate(http_request_duration_seconds_count[1m])

# Memory usage per pod
container_memory_usage_bytes{namespace="todo-helm"}

# CPU usage
rate(container_cpu_usage_seconds_total{namespace="todo-helm"}[1m])
```

---

## Security Decisions

**Non-root containers:** The app container runs as uid 1000. If a vulnerability is exploited, the attacker does not gain root access to the node.

```dockerfile
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser
```

**Secrets vs ConfigMaps:** Database passwords are stored in Kubernetes Secrets (base64 encoded), not ConfigMaps. Sensitive data never appears in application configuration files.

**Resource limits:** Every container has defined CPU and memory limits. Without these, a single misbehaving pod can starve all other workloads on the node.

**PostgreSQL fsGroup:** Rather than forcing a specific runAsUser (which breaks PostgreSQL's internal permission model), we use `fsGroup: 70` to ensure the postgres user owns the data volume.

---

## Why These Technologies

**k3d over minikube:** k3d runs k3s inside Docker, matching the same distribution used in many production edge and IoT environments. It starts in seconds and supports multi-node clusters.

**Helm over raw kubectl apply:** Raw manifests are static. Helm templates allow the same configuration to be deployed to multiple environments with different values. The release history enables instant rollbacks.

**kube-prometheus-stack:** Installs Prometheus, Grafana, and Alertmanager as a single unit with pre-built dashboards for Kubernetes. It uses the Operator pattern, which is the production standard for managing stateful monitoring infrastructure.

**prometheus-fastapi-instrumentator:** Automatically instruments all FastAPI routes with request count, latency histograms, and in-progress request gauges — without writing any custom metric code.

---

## License

MIT
