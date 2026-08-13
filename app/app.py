from datetime import datetime

from flask import Flask, jsonify, Response, request, render_template
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException

app = Flask(__name__)

REQUEST_COUNT = Counter(
    "pfa_http_requests_total",
    "Nombre total de requêtes HTTP reçues par l'application",
    ["method", "endpoint", "http_status"]
)

K8S_PODS_TOTAL = Gauge(
    "cloudops_kubernetes_pods_total",
    "Nombre total de pods observés par le CloudOps Dashboard",
    ["namespace", "status"]
)

K8S_SERVICES_TOTAL = Gauge(
    "cloudops_kubernetes_services_total",
    "Nombre total de services Kubernetes observés",
    ["namespace"]
)

WATCHED_NAMESPACES = ["default", "argocd", "monitoring", "nginx-gateway"]


def load_kubernetes_config():
    try:
        config.load_incluster_config()
        return "in-cluster"
    except ConfigException:
        try:
            config.load_kube_config()
            return "local-kubeconfig"
        except ConfigException:
            return "unavailable"


@app.after_request
def count_requests(response):
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.path,
        http_status=response.status_code
    ).inc()
    return response


def get_platform_status():
    config_mode = load_kubernetes_config()

    if config_mode == "unavailable":
        return {
            "platform_status": "Unavailable",
            "config_mode": config_mode,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "namespaces": [],
            "pods": [],
            "services": [],
            "deployments": [],
            "summary": {
                "namespaces": 0,
                "pods": 0,
                "services": 0,
                "deployments": 0,
                "running_pods": 0,
                "problem_pods": 0
            }
        }

    v1 = client.CoreV1Api()
    apps_v1 = client.AppsV1Api()

    pods = []
    services = []
    deployments = []

    total_running = 0
    total_problem = 0

    K8S_PODS_TOTAL.clear()
    K8S_SERVICES_TOTAL.clear()

    for namespace in WATCHED_NAMESPACES:
        try:
            pod_list = v1.list_namespaced_pod(namespace=namespace)
            status_count = {}

            for pod in pod_list.items:
                pod_status = pod.status.phase

                if pod_status == "Running":
                    total_running += 1
                else:
                    total_problem += 1

                status_count[pod_status] = status_count.get(pod_status, 0) + 1

                pods.append({
                    "namespace": namespace,
                    "name": pod.metadata.name,
                    "status": pod_status,
                    "node": pod.spec.node_name or "-",
                    "restart_count": sum(
                        container.restart_count for container in (pod.status.container_statuses or [])
                    )
                })

            for status, count in status_count.items():
                K8S_PODS_TOTAL.labels(namespace=namespace, status=status).set(count)

        except Exception as e:
            total_problem += 1
            pods.append({
                "namespace": namespace,
                "name": "Erreur lecture pods",
                "status": str(e),
                "node": "-",
                "restart_count": 0
            })

        try:
            service_list = v1.list_namespaced_service(namespace=namespace)
            K8S_SERVICES_TOTAL.labels(namespace=namespace).set(len(service_list.items))

            for service in service_list.items:
                services.append({
                    "namespace": namespace,
                    "name": service.metadata.name,
                    "type": service.spec.type,
                    "cluster_ip": service.spec.cluster_ip or "-"
                })

        except Exception as e:
            services.append({
                "namespace": namespace,
                "name": "Erreur lecture services",
                "type": str(e),
                "cluster_ip": "-"
            })

        try:
            deployment_list = apps_v1.list_namespaced_deployment(namespace=namespace)

            for deployment in deployment_list.items:
                desired = deployment.spec.replicas or 0
                available = deployment.status.available_replicas or 0

                deployments.append({
                    "namespace": namespace,
                    "name": deployment.metadata.name,
                    "desired_replicas": desired,
                    "available_replicas": available,
                    "status": "Healthy" if desired == available else "Warning"
                })

        except Exception as e:
            deployments.append({
                "namespace": namespace,
                "name": "Erreur lecture deployments",
                "desired_replicas": 0,
                "available_replicas": 0,
                "status": str(e)
            })

    platform_status = "Healthy" if total_problem == 0 else "Warning"

    return {
        "platform_status": platform_status,
        "config_mode": config_mode,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "namespaces": WATCHED_NAMESPACES,
        "pods": pods,
        "services": services,
        "deployments": deployments,
        "summary": {
            "namespaces": len(WATCHED_NAMESPACES),
            "pods": len(pods),
            "services": len(services),
            "deployments": len(deployments),
            "running_pods": total_running,
            "problem_pods": total_problem
        }
    }


@app.route("/")
def home():
    return render_template("dashboard.html")


@app.route("/api/platform-status")
def api_platform_status():
    return jsonify(get_platform_status()), 200


@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "service": "cloudops-dashboard",
        "version": "4.0.0"
    }), 200


@app.route("/metrics")
def metrics():
    get_platform_status()
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)