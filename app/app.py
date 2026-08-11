from flask import Flask, render_template_string, jsonify, Response, request
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

REQUEST_COUNT = Counter(
    "pfa_http_requests_total",
    "Nombre total de requêtes HTTP reçues par l'application",
    ["method", "endpoint", "http_status"]
)

tickets = [
    {"id": 1, "titre": "Problème réseau", "statut": "Ouvert"},
    {"id": 2, "titre": "Demande accès application", "statut": "En cours"},
    {"id": 3, "titre": "Erreur serveur", "statut": "Résolu"},
]


@app.after_request
def count_requests(response):
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.path,
        http_status=response.status_code
    ).inc()
    return response


@app.route("/")
def home():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>PFA DevOps Cloud-Native</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 40px;
                background: #f4f6f8;
            }
            h1 {
                color: #1f2937;
            }
            .container {
                background: white;
                padding: 25px;
                border-radius: 10px;
                width: 85%;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
            }
            th, td {
                padding: 12px;
                border: 1px solid #ddd;
                text-align: left;
            }
            th {
                background: #1f2937;
                color: white;
            }
            .badge {
                padding: 5px 10px;
                border-radius: 12px;
                background: #e5e7eb;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Application de gestion des tickets</h1>
            <p>Projet PFA : Chaîne DevOps Cloud-Native avec CI/CD, Kubernetes, GitOps et Monitoring.</p>

            <table>
                <tr>
                    <th>ID</th>
                    <th>Titre</th>
                    <th>Statut</th>
                </tr>
                {% for ticket in tickets %}
                <tr>
                    <td>{{ ticket.id }}</td>
                    <td>{{ ticket.titre }}</td>
                    <td><span class="badge">{{ ticket.statut }}</span></td>
                </tr>
                {% endfor %}
            </table>
        </div>
    </body>
    </html>
    """
    return render_template_string(html, tickets=tickets)


@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "service": "pfa-ticket-app",
        "version": "1.0.0"
    }), 200


@app.route("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)