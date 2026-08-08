from flask import Flask, render_template_string, jsonify

app = Flask(__name__)

tickets = [
    {"id": 1, "titre": "Problème réseau", "statut": "Ouvert"},
    {"id": 2, "titre": "Demande accès application", "statut": "En cours"},
    {"id": 3, "titre": "Erreur serveur", "statut": "Résolu"},
]

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
            <p>Projet PFA : Chaîne DevOps Cloud-Native avec CI/CD, Kubernetes et GitOps.</p>

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)