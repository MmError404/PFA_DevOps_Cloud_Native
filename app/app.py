from flask import Flask, jsonify, Response, request, render_template_string
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
            "platform_status": "unavailable",
            "message": "Configuration Kubernetes non disponible",
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
                    "node": pod.spec.node_name,
                    "restart_count": sum(
                        container.restart_count for container in (pod.status.container_statuses or [])
                    )
                })

            for status, count in status_count.items():
                K8S_PODS_TOTAL.labels(namespace=namespace, status=status).set(count)

        except Exception as e:
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
                    "cluster_ip": service.spec.cluster_ip
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
    html = """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <title>CloudOps Dashboard</title>
        <style>
            body {
                margin: 0;
                font-family: Arial, sans-serif;
                background: #f3f4f6;
                color: #111827;
            }

            header {
                background: #111827;
                color: white;
                padding: 25px 40px;
            }

            header h1 {
                margin: 0;
                font-size: 30px;
            }

            header p {
                color: #d1d5db;
                margin-top: 8px;
            }

            .container {
                width: 92%;
                margin: 25px auto;
            }

            .cards {
                display: grid;
                grid-template-columns: repeat(5, 1fr);
                gap: 15px;
                margin-bottom: 25px;
            }

            .card {
                background: white;
                padding: 20px;
                border-radius: 12px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
            }

            .card h3 {
                margin: 0;
                color: #6b7280;
                font-size: 14px;
            }

            .card p {
                font-size: 28px;
                font-weight: bold;
                margin: 10px 0 0;
            }

            .section {
                background: white;
                padding: 20px;
                border-radius: 12px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                margin-bottom: 25px;
            }

            table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 10px;
            }

            th, td {
                padding: 11px;
                border-bottom: 1px solid #e5e7eb;
                text-align: left;
                font-size: 14px;
            }

            th {
                background: #111827;
                color: white;
            }

            .badge {
                padding: 5px 10px;
                border-radius: 20px;
                font-size: 13px;
                font-weight: bold;
            }

            .healthy {
                background: #dcfce7;
                color: #166534;
            }

            .warning {
                background: #fef3c7;
                color: #92400e;
            }

            .down {
                background: #fee2e2;
                color: #991b1b;
            }

            .footer {
                text-align: center;
                color: #6b7280;
                margin: 25px;
                font-size: 14px;
            }
        </style>
    </head>

    <body>
        <header>
            <h1>CloudOps Dashboard</h1>
            <p>Supervision temps réel d'une plateforme DevOps Cloud-Native</p>
        </header>

        <div class="container">
            <div class="cards">
                <div class="card">
                    <h3>Statut plateforme</h3>
                    <p id="platform_status">...</p>
                </div>
                <div class="card">
                    <h3>Namespaces</h3>
                    <p id="namespaces">0</p>
                </div>
                <div class="card">
                    <h3>Pods</h3>
                    <p id="pods">0</p>
                </div>
                <div class="card">
                    <h3>Services</h3>
                    <p id="services">0</p>
                </div>
                <div class="card">
                    <h3>Deployments</h3>
                    <p id="deployments">0</p>
                </div>
            </div>

            <div class="section">
                <h2>Deployments Kubernetes</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Namespace</th>
                            <th>Nom</th>
                            <th>Replicas désirés</th>
                            <th>Replicas disponibles</th>
                            <th>Statut</th>
                        </tr>
                    </thead>
                    <tbody id="deployments_table"></tbody>
                </table>
            </div>

            <div class="section">
                <h2>Pods Kubernetes</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Namespace</th>
                            <th>Nom du pod</th>
                            <th>Statut</th>
                            <th>Node</th>
                            <th>Restarts</th>
                        </tr>
                    </thead>
                    <tbody id="pods_table"></tbody>
                </table>
            </div>

            <div class="section">
                <h2>Services Kubernetes</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Namespace</th>
                            <th>Nom</th>
                            <th>Type</th>
                            <th>Cluster IP</th>
                        </tr>
                    </thead>
                    <tbody id="services_table"></tbody>
                </table>
            </div>

            <div class="footer">
                Version 3.0.0 — Flask + Kubernetes API + Prometheus + Grafana
            </div>
        </div>

        <script>
            function badgeClass(status) {
                if (status === "Running" || status === "Healthy") {
                    return "badge healthy";
                }
                if (status === "Warning" || status === "Pending") {
                    return "badge warning";
                }
                return "badge down";
            }

            async function loadStatus() {
                const response = await fetch("/api/platform-status");
                const data = await response.json();

                document.getElementById("platform_status").innerText = data.platform_status;
                document.getElementById("namespaces").innerText = data.summary.namespaces;
                document.getElementById("pods").innerText = data.summary.pods;
                document.getElementById("services").innerText = data.summary.services;
                document.getElementById("deployments").innerText = data.summary.deployments;

                let deploymentsHtml = "";
                data.deployments.forEach(dep => {
                    deploymentsHtml += `
                        <tr>
                            <td>${dep.namespace}</td>
                            <td>${dep.name}</td>
                            <td>${dep.desired_replicas}</td>
                            <td>${dep.available_replicas}</td>
                            <td><span class="${badgeClass(dep.status)}">${dep.status}</span></td>
                        </tr>
                    `;
                });
                document.getElementById("deployments_table").innerHTML = deploymentsHtml;

                let podsHtml = "";
                data.pods.forEach(pod => {
                    podsHtml += `
                        <tr>
                            <td>${pod.namespace}</td>
                            <td>${pod.name}</td>
                            <td><span class="${badgeClass(pod.status)}">${pod.status}</span></td>
                            <td>${pod.node}</td>
                            <td>${pod.restart_count}</td>
                        </tr>
                    `;
                });
                document.getElementById("pods_table").innerHTML = podsHtml;

                let servicesHtml = "";
                data.services.forEach(service => {
                    servicesHtml += `
                        <tr>
                            <td>${service.namespace}</td>
                            <td>${service.name}</td>
                            <td>${service.type}</td>
                            <td>${service.cluster_ip}</td>
                        </tr>
                    `;
                });
                document.getElementById("services_table").innerHTML = servicesHtml;
            }

            loadStatus();
            setInterval(loadStatus, 10000);
        </script>
    </body>
    </html>
    """

    return render_template_string(html)


@app.route("/api/platform-status")
def api_platform_status():
    return jsonify(get_platform_status()), 200


@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "service": "cloudops-dashboard",
        "version": "3.0.0"
    }), 200


@app.route("/metrics")
def metrics():
    get_platform_status()
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)