import threading
import sqlite3
import webview
import sys
import os
from flask import Flask, render_template_string, jsonify, request
from playwright.sync_api import sync_playwright

app = Flask(__name__)

# Configuração do Banco de Dados SQLite
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_NAME = os.path.join(BASE_DIR, "zap_crm.db")

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            status TEXT DEFAULT 'Aguardando',
            last_message TEXT,
            reminder TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Função para abrir o WhatsApp Web usando Playwright de forma real
def launch_whatsapp_web():
    try:
        def run_pw():
            with sync_playwright() as p:
                user_data = os.path.join(BASE_DIR, "whatsapp_session")
                # Abre o navegador com sessão persistente para salvar o login do QR Code
                browser = p.chromium.launch_persistent_context(
                    user_data_dir=user_data,
                    headless=False,
                    args=["--start-maximized"]
                )
                page = browser.pages[0] if browser.pages else browser.new_page()
                page.goto("https://web.whatsapp.com")
                # Mantém o processo rodando enquanto a janela estiver aberta
                input("Pressione Enter no terminal para fechar o navegador do WhatsApp...")
        
        t = threading.Thread(target=run_pw, daemon=True)
        t.start()
        return True
    except Exception as e:
        print("Erro ao abrir Playwright:", e)
        return False

# Interface HTML / CSS / JS Integrada com CRUD Completo
HTML_PAGE = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ZapCRM Local</title>
    <style>
        :root {
            --bg: #0b0f19;
            --card-bg: #111827;
            --text: #f8fafc;
            --text-muted: #94a3b8;
            --primary: #25d366;
            --primary-hover: #1ebd5a;
            --danger: #ef4444;
            --danger-hover: #dc2626;
            --warning: #f59e0b;
            --safe: #10b981;
            --border: #1f2937;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
        body { background-color: var(--bg); color: var(--text); min-height: 100vh; display: flex; justify-content: center; align-items: center; padding: 20px; }
        .app-container { width: 100%; max-width: 950px; display: flex; flex-direction: column; gap: 20px; }
        .app-header { display: flex; justify-content: space-between; align-items: center; }
        .app-header h1 { font-size: 1.4rem; font-weight: 700; color: #fff; }
        .app-header p { font-size: 0.8rem; color: var(--text-muted); }
        
        .btn-action { background-color: var(--primary); color: #000; border: none; padding: 8px 14px; border-radius: 8px; font-weight: 700; font-size: 0.8rem; cursor: pointer; transition: background 0.2s; }
        .btn-action:hover { background-color: var(--primary-hover); }
        
        .dashboard-grid { display: grid; grid-template-columns: 1fr 2fr; gap: 20px; }
        .card { background-color: var(--card-bg); border: 1px solid var(--border); border-radius: 16px; padding: 20px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.3); height: 520px; display: flex; flex-direction: column; }
        .card h2 { font-size: 0.9rem; font-weight: 600; margin-bottom: 12px; color: #e2e8f0; text-transform: uppercase; letter-spacing: 0.5px; }
        
        ul { list-style: none; display: flex; flex-direction: column; gap: 8px; overflow-y: auto; flex-grow: 1; padding-right: 4px; }
        li { background: #090d16; padding: 12px; border-radius: 10px; border: 1px solid var(--border); cursor: pointer; transition: border-color 0.2s; }
        li:hover, li.active { border-color: var(--primary); }
        
        .contact-name { font-size: 0.9rem; font-weight: 600; color: #fff; }
        .contact-preview { font-size: 0.75rem; color: var(--text-muted); margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        
        .badge { font-size: 0.65rem; padding: 2px 6px; border-radius: 4px; font-weight: 600; display: inline-block; margin-top: 6px; }
        .badge.Urgente { background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.2); color: #f87171; }
        .badge.Aguardando { background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.2); color: #fbbf24; }
        .badge.Fechado { background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.2); color: #34d399; }

        .chat-details { display: flex; flex-direction: column; gap: 10px; height: 100%; justify-content: space-between; }
        .details-info { display: flex; flex-direction: column; gap: 6px; }
        .details-info label { font-size: 0.75rem; color: var(--text-muted); }
        .details-info input, .details-info select, .details-info textarea { padding: 8px 12px; background: #090d16; border: 1px solid var(--border); border-radius: 8px; color: #fff; font-size: 0.85rem; outline: none; }
        .details-info textarea { resize: none; height: 70px; }
        
        .btn-group { display: flex; gap: 8px; margin-top: 4px; }
        .btn-save { background-color: var(--primary); color: #000; border: none; padding: 8px; border-radius: 8px; font-weight: 700; font-size: 0.8rem; cursor: pointer; flex: 1; }
        .btn-delete { background-color: var(--danger); color: #fff; border: none; padding: 8px; border-radius: 8px; font-weight: 700; font-size: 0.8rem; cursor: pointer; }
        .btn-delete:hover { background-color: var(--danger-hover); }

        /* Modal Novo Contato */
        .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.7); justify-content: center; align-items: center; }
        .modal-content { background: var(--card-bg); padding: 25px; border-radius: 16px; width: 400px; border: 1px solid var(--border); display: flex; flex-direction: column; gap: 12px; }
        .modal-content h2 { font-size: 1rem; color: #fff; }
        .modal-content input, .modal-content select { padding: 10px; background: #090d16; border: 1px solid var(--border); border-radius: 8px; color: #fff; outline: none; font-size: 0.85rem; }
    </style>
</head>
<body>
    <div class="app-container">
        <header class="app-header">
            <div>
                <h1>💬 ZapCRM Local</h1>
                <p>Gestão de Conversas & Playwright Integrado</p>
            </div>
            <div style="display: flex; gap: 10px;">
                <button class="btn-action" onclick="openWhatsApp()">🚀 Abrir WhatsApp Web</button>
                <button class="btn-action" style="background: #3b82f6; color:#fff;" onclick="openModal()">➕ Novo Contato</button>
            </div>
        </header>
        
        <div class="dashboard-grid">
            <section class="card">
                <h2>Conversas Cadastradas</h2>
                <ul id="contactList"></ul>
            </section>

            <section class="card">
                <h2>Gerenciar Contato (CRUD)</h2>
                <div id="contactDetails" class="chat-details">
                    <p style="color: var(--text-muted); font-size: 0.85rem; text-align: center; margin: auto;">Selecione uma conversa ao lado para editar ou excluir.</p>
                </div>
            </section>
        </div>
    </div>

    <!-- Modal Novo Contato -->
    <div id="contactModal" class="modal">
        <div class="modal-content">
            <h2>Adicionar Novo Contato / Chat</h2>
            <input type="text" id="newName" placeholder="Nome do Contato" autocomplete="off">
            <input type="text" id="newPhone" placeholder="Telefone (Ex: +55 11 99999-9999)" autocomplete="off">
            <select id="newStatus">
                <option value="Aguardando">Aguardando</option>
                <option value="Urgente">Urgente</option>
                <option value="Fechado">Fechado</option>
            </select>
            <input type="text" id="newReminder" placeholder="Lembrete / Prazo (Ex: Retornar às 14h)" autocomplete="off">
            <div style="display: flex; gap: 8px; margin-top: 10px;">
                <button class="btn-save" onclick="createContact()">Salvar</button>
                <button class="btn-delete" onclick="closeModal()" style="background:#374151;">Cancelar</button>
            </div>
        </div>
    </div>

    <script>
        let selectedContactId = null;
        let allContacts = [];

        async function fetchContacts() {
            const res = await fetch('/api/contacts');
            allContacts = await res.json();
            const list = document.getElementById('contactList');
            list.innerHTML = '';

            if (allContacts.length === 0) {
                list.innerHTML = '<li style="text-align:center; color: var(--text-muted); border:none; background:transparent;">Nenhum contato cadastrado.</li>';
                return;
            }

            allContacts.forEach(c => {
                const li = document.createElement('li');
                li.className = c.id === selectedContactId ? 'active' : '';
                li.innerHTML = `
                    <div class="contact-name">${escapeHtml(c.name)}</div>
                    <div class="contact-preview">${escapeHtml(c.last_message || 'Sem mensagens')}</div>
                    <span class="badge ${c.status}">${c.status}</span>
                `;
                li.onclick = () => selectContact(c.id);
                list.appendChild(li);
            });
        }

        function selectContact(id) {
            selectedContactId = id;
            fetchContacts();
            const c = allContacts.find(item => item.id === id);
            if (!c) return;

            const details = document.getElementById('contactDetails');
            details.innerHTML = `
                <div class="details-info">
                    <label>Nome:</label>
                    <input type="text" id="editName" value="${escapeHtml(c.name)}">
                    
                    <label>Telefone:</label>
                    <input type="text" id="editPhone" value="${escapeHtml(c.phone)}">
                    
                    <label>Status:</label>
                    <select id="editStatus">
                        <option value="Aguardando" ${c.status === 'Aguardando' ? 'selected' : ''}>Aguardando</option>
                        <option value="Urgente" ${c.status === 'Urgente' ? 'selected' : ''}>Urgente</option>
                        <option value="Fechado" ${c.status === 'Fechado' ? 'selected' : ''}>Fechado</option>
                    </select>

                    <label>Última Mensagem Resumo:</label>
                    <textarea id="editMessage">${escapeHtml(c.last_message || '')}</textarea>

                    <label>Lembrete:</label>
                    <input type="text" id="editReminder" value="${escapeHtml(c.reminder || '')}">
                </div>
                <div class="btn-group">
                    <button class="btn-save" onclick="updateContact(${c.id})">💾 Salvar Alterações</button>
                    <button class="btn-delete" onclick="deleteContact(${c.id})">🗑️ Excluir</button>
                </div>
            `;
        }

        async function createContact() {
            const name = document.getElementById('newName').value.trim();
            const phone = document.getElementById('newPhone').value.trim();
            const status = document.getElementById('newStatus').value;
            const reminder = document.getElementById('newReminder').value.trim();

            if (!name || !phone) {
                alert('Preencha o nome e o telefone.');
                return;
            }

            await fetch('/api/contacts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, phone, status, reminder, last_message: 'Novo chat criado' })
            });

            closeModal();
            fetchContacts();
        }

        async function updateContact(id) {
            const name = document.getElementById('editName').value.trim();
            const phone = document.getElementById('editPhone').value.trim();
            const status = document.getElementById('editStatus').value;
            const last_message = document.getElementById('editMessage').value.trim();
            const reminder = document.getElementById('editReminder').value.trim();

            await fetch(`/api/contacts/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, phone, status, last_message, reminder })
            });

            alert('Contato atualizado com sucesso!');
            fetchContacts();
        }

        async function deleteContact(id) {
            if (!confirm('Tem certeza que deseja excluir este contato?')) return;

            await fetch(`/api/contacts/${id}`, { method: 'DELETE' });
            selectedContactId = null;
            document.getElementById('contactDetails').innerHTML = '<p style="color: var(--text-muted); font-size: 0.85rem; text-align: center; margin: auto;">Selecione uma conversa ao lado para editar ou excluir.</p>';
            fetchContacts();
        }

        async function openWhatsApp() {
            const res = await fetch('/api/whatsapp/open', { method: 'POST' });
            const data = await res.json();
            if (data.status === 'success') {
                alert('O navegador do WhatsApp Web foi iniciado no seu computador!');
            } else {
                alert('Erro ao iniciar o WhatsApp Web.');
            }
        }

        function openModal() {
            document.getElementById('newName').value = '';
            document.getElementById('newPhone').value = '';
            document.getElementById('newReminder').value = '';
            document.getElementById('contactModal').style.display = 'flex';
        }

        function closeModal() {
            document.getElementById('contactModal').style.display = 'none';
        }

        function escapeHtml(str) {
            if (!str) return '';
            return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        }

        fetchContacts();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

# --- ROTAS DE CRUD ---

@app.route('/api/contacts', methods=['GET', 'POST'])
def manage_contacts():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if request.method == 'POST':
        data = request.json
        cursor.execute('''
            INSERT INTO contacts (name, phone, status, last_message, reminder) 
            VALUES (?, ?, ?, ?, ?)
        ''', (data.get('name'), data.get('phone'), data.get('status', 'Aguardando'), data.get('last_message', ''), data.get('reminder', '')))
        conn.commit()
        conn.close()
        return jsonify({"status": "created"})

    cursor.execute('SELECT * FROM contacts')
    rows = cursor.fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

@app.route('/api/contacts/<int:contact_id>', methods=['PUT', 'DELETE'])
def modify_contact(contact_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    if request.method == 'PUT':
        data = request.json
        cursor.execute('''
            UPDATE contacts 
            SET name = ?, phone = ?, status = ?, last_message = ?, reminder = ? 
            WHERE id = ?
        ''', (data.get('name'), data.get('phone'), data.get('status'), data.get('last_message'), data.get('reminder'), contact_id))
        conn.commit()
        conn.close()
        return jsonify({"status": "updated"})

    if request.method == 'DELETE':
        cursor.execute('DELETE FROM contacts WHERE id = ?', (contact_id,))
        conn.commit()
        conn.close()
        return jsonify({"status": "deleted"})

@app.route('/api/whatsapp/open', methods=['POST'])
def trigger_whatsapp():
    success = launch_whatsapp_web()
    if success:
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 500

if __name__ == '__main__':
    def run_flask():
        app.run(port=5000, debug=False, use_reloader=False)

    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

    webview.create_window("ZapCRM Local", "http://127.0.0.1:5000", width=980, height=620)
    webview.start()