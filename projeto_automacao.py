import os
import re
import json
import sqlite3
import time
import threading
from datetime import datetime
import pandas as pd
 
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
 
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
 
# ==========================================
# 1. BANCO DE DADOS (SQLite)
# ==========================================
DB_NAME = "historico.db"
 
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
 
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS buscas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            termo TEXT NOT NULL,
            data_hora DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
 
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            busca_id INTEGER,
            titulo TEXT,
            preco REAL,
            link TEXT,
            FOREIGN KEY (busca_id) REFERENCES buscas (id)
        )
    """)
 
    conn.commit()
    conn.close()
 
def salvar_no_banco(termo: str, lista_produtos: list):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
 
    data_formatada = datetime.now().strftime("%d/%m/%Y %H:%M")
    cursor.execute("INSERT INTO buscas (termo, data_hora) VALUES (?, ?)", (termo, data_formatada))
    busca_id = cursor.lastrowid
 
    for item in lista_produtos:
        cursor.execute(
            "INSERT INTO produtos (busca_id, titulo, preco, link) VALUES (?, ?, ?, ?)",
            (busca_id, item["titulo"], item["preco"], item["link"])
        )
 
    conn.commit()
    conn.close()
 
def obter_historico_completo():
    conn = sqlite3.connect(DB_NAME)
    query = """
        SELECT b.data_hora, b.termo, p.titulo, p.preco, p.link
        FROM produtos p
        JOIN buscas b ON p.busca_id = b.id
        ORDER BY p.id DESC
    """
    cursor = conn.cursor()
    cursor.execute(query)
    registros = cursor.fetchall()
    conn.close()
    return registros
 
def obter_df_historico():
    conn = sqlite3.connect(DB_NAME)
    query = """
        SELECT b.data_hora AS 'Data/Hora', b.termo AS 'Termo Pesquisado',
               p.titulo AS 'Produto', p.preco AS 'Preço (R$)', p.link AS 'Link'
        FROM produtos p
        JOIN buscas b ON p.busca_id = b.id
        ORDER BY p.id DESC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df
 
# ==========================================
# 2. AUTOMAÇÃO WEB (Selenium)
# ==========================================
def executar_scraping(termo: str, limite: int = 10, callback_status=None):
    if callback_status:
        callback_status("Iniciando Chrome...")
 
    options = Options()
    options.add_argument("--window-size=1280,800")
    # REMOVIDO --user-data-dir apontando pro seu perfil real do Chrome.
    # Reutilizar o perfil pessoal trava com "session not created: Chrome
    # failed to start: crashed" se o Chrome já estiver aberto (ou algum
    # processo dele ainda rodando em segundo plano) usando esse mesmo
    # perfil. Como essa busca é numa página pública (não precisa de
    # login), deixamos o Selenium abrir com um perfil temporário e
    # limpo, sem esse risco de conflito.
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
 
    driver = webdriver.Chrome(options=options)
    produtos_coletados = []
 
    try:
        if callback_status:
            callback_status(f"Acessando Mercado Livre para '{termo}'...")
 
        termo_url = termo.replace(" ", "-").lower()
        driver.get(f"https://lista.mercadolivre.com.br/{termo_url}")
        time.sleep(3)
 
        # Rolagem suave para carregar os elementos
        driver.execute_script("window.scrollTo(0, 600);")
        time.sleep(2)
 
        cards = driver.find_elements(
            By.CSS_SELECTOR,
            "li.ui-search-layout__item, div.poly-card, div.ui-search-result__content, .ui-search-result"
        )
 
        if callback_status:
            callback_status(f"Lendo {len(cards)} itens e extraindo preços...")
 
        for card in cards[:limite]:
            try:
                # 1. Extração do Título
                titulo = ""
                for sel in [".poly-component__title", ".ui-search-item__title", "h2", "a.poly-component__title"]:
                    elems = card.find_elements(By.CSS_SELECTOR, sel)
                    if elems and elems[0].text.strip():
                        titulo = elems[0].text.strip()
                        break
 
                # 2. Extração do Link
                link_elem = card.find_elements(By.TAG_NAME, "a")
                link = link_elem[0].get_attribute("href") if link_elem else ""
 
                # 3. Extração do Preço Robusta (Seletores CSS + Fallback por Regex)
                preco_num = 0.0
                for sel in [
                    ".poly-price__current .andromeda-money-amount__fraction",
                    ".poly-component__price .andromeda-money-amount__fraction",
                    ".andromeda-money-amount__fraction",
                    ".price-tag-fraction",
                    ".poly-price__current"
                ]:
                    elems = card.find_elements(By.CSS_SELECTOR, sel)
                    if elems and elems[0].text.strip():
                        txt = elems[0].text.replace(".", "").replace("R$", "").strip()
                        match = re.search(r'\d+', txt)
                        if match:
                            preco_num = float(match.group())
                            break
 
                # Fallback: Se o seletor falhar, busca "R$ XX" no texto bruto do card
                if preco_num == 0.0:
                    match_fallback = re.search(r'R\$\s*([\d\.]+)', card.text)
                    if match_fallback:
                        try:
                            preco_num = float(match_fallback.group(1).replace(".", ""))
                        except Exception:
                            pass
 
                if titulo:
                    produtos_coletados.append({
                        "titulo": titulo,
                        "preco": preco_num,
                        "link": link
                    })
            except Exception:
                continue
    finally:
        driver.quit()
 
    return produtos_coletados
 
# ==========================================
# 3. INTERFACE GRÁFICA (Tkinter)
# ==========================================
class AppAutomação:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema de Automação de Preços & Banco de Dados")
        self.root.geometry("950x600")
        self.root.config(bg="#f4f6f9")
 
        init_db()
        self.criar_interface()
 
    def criar_interface(self):
        # Título principal
        lbl_titulo = tk.Label(
            self.root, text="🤖 Automação Web & Histórico Local (SQLite)",
            font=("Helvetica", 15, "bold"), bg="#f4f6f9", fg="#333"
        )
        lbl_titulo.pack(pady=10)
 
        # Painel de Busca
        frame_busca = tk.Frame(self.root, bg="#f4f6f9")
        frame_busca.pack(pady=5)
 
        tk.Label(frame_busca, text="Produto:", font=("Arial", 11), bg="#f4f6f9").pack(side=tk.LEFT, padx=5)
 
        self.ent_busca = tk.Entry(frame_busca, font=("Arial", 11), width=30)
        self.ent_busca.pack(side=tk.LEFT, padx=5)
        # CORRIGIDO: bind precisa de um evento nomeado, não uma string vazia.
        # "<Return>" faz a busca disparar quando o usuário aperta Enter.
        self.ent_busca.bind("<Return>", lambda e: self.iniciar_busca_thread())
 
        self.btn_buscar = tk.Button(
            frame_busca, text="🔍 Nova Pesquisa", font=("Arial", 10, "bold"),
            bg="#28a745", fg="white", padx=10, command=self.iniciar_busca_thread
        )
        self.btn_buscar.pack(side=tk.LEFT, padx=5)
 
        # Status
        self.lbl_status = tk.Label(self.root, text="Status: Pronto", font=("Arial", 10, "italic"), bg="#f4f6f9", fg="#555")
        self.lbl_status.pack(pady=5)
 
        # Tabela (Treeview)
        frame_tabela = tk.Frame(self.root)
        frame_tabela.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
 
        colunas = ("Data/Hora", "Termo", "Produto", "Preço (R$)", "Link")
        self.tree = ttk.Treeview(frame_tabela, columns=colunas, show="headings", height=12)
 
        self.tree.heading("Data/Hora", text="Data/Hora")
        self.tree.heading("Termo", text="Termo")
        self.tree.heading("Produto", text="Produto")
        # CORRIGIDO: removidas as barras invertidas soltas ("\(" e "\)"),
        # que geravam SyntaxWarning e não batiam com o nome da coluna
        # definido em 'colunas' acima.
        self.tree.heading("Preço (R$)", text="Preço (R$)")
        self.tree.heading("Link", text="Link")
 
        self.tree.column("Data/Hora", width=110, anchor="center")
        self.tree.column("Termo", width=110)
        self.tree.column("Produto", width=320)
        self.tree.column("Preço (R$)", width=100, anchor="center")
        self.tree.column("Link", width=260)
 
        scrollbar = ttk.Scrollbar(frame_tabela, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
 
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
 
        # Painel Inferior de Ações e Histórico
        frame_acoes = tk.Frame(self.root, bg="#f4f6f9")
        frame_acoes.pack(pady=10)
 
        btn_ver_banco = tk.Button(
            frame_acoes, text="📜 Carregar Histórico do Banco",
            font=("Arial", 10), bg="#17a2b8", fg="white", padx=10, command=self.carregar_historico_banco
        )
        btn_ver_banco.pack(side=tk.LEFT, padx=5)
 
        btn_abrir_excel = tk.Button(
            frame_acoes, text="📂 Abrir e Ler Planilha Excel",
            font=("Arial", 10), bg="#ffc107", fg="#333", padx=10, command=self.abrir_arquivo_excel
        )
        btn_abrir_excel.pack(side=tk.LEFT, padx=5)
 
        btn_exportar = tk.Button(
            frame_acoes, text="📊 Exportar para Excel",
            font=("Arial", 10, "bold"), bg="#007bff", fg="white", padx=10, command=self.exportar_excel
        )
        btn_exportar.pack(side=tk.LEFT, padx=5)
 
        btn_exportar_json = tk.Button(
            frame_acoes, text="🧾 Exportar para JSON",
            font=("Arial", 10, "bold"), bg="#6f42c1", fg="white", padx=10, command=self.exportar_json
        )
        btn_exportar_json.pack(side=tk.LEFT, padx=5)
 
        btn_ver_exportacoes = tk.Button(
            frame_acoes, text="🗂️ Ver Exportações",
            font=("Arial", 10), bg="#20c997", fg="white", padx=10, command=self.ver_exportacoes
        )
        btn_ver_exportacoes.pack(side=tk.LEFT, padx=5)
 
    def atualizar_status(self, mensagem: str):
        self.lbl_status.config(text=f"Status: {mensagem}")
        self.root.update_idletasks()
 
    def limpar_tabela(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
 
    def iniciar_busca_thread(self):
        termo = self.ent_busca.get().strip()
        if not termo:
            messagebox.showwarning("Aviso", "Por favor, digite um produto para pesquisar.")
            return
 
        self.btn_buscar.config(state=tk.DISABLED)
        threading.Thread(target=self.rodar_automacao, args=(termo,), daemon=True).start()
 
    def rodar_automacao(self, termo: str):
        try:
            resultados = executar_scraping(termo, limite=10, callback_status=self.atualizar_status)
 
            if resultados:
                self.atualizar_status("Salvando no Banco SQLite...")
                salvar_no_banco(termo, resultados)
 
                # Mostra só os resultados desta busca — o histórico completo
                # (buscas anteriores) só aparece se o usuário clicar em
                # "Carregar Histórico do Banco" explicitamente.
                self.exibir_resultados_busca(termo, resultados)
                self.atualizar_status("✅ Concluído com sucesso!")
                messagebox.showinfo("Sucesso", f"Busca concluída!\n{len(resultados)} produtos encontrados e gravados no banco.")
            else:
                self.atualizar_status("Nenhum resultado encontrado.")
                messagebox.showwarning("Aviso", "Nenhum resultado foi retornado.")
        except Exception as e:
            self.atualizar_status("Erro durante a execução.")
            messagebox.showerror("Erro", f"Ocorreu um erro: {str(e)}")
        finally:
            self.btn_buscar.config(state=tk.NORMAL)
 
    def exibir_resultados_busca(self, termo: str, resultados: list):
        """Mostra na tabela apenas os produtos encontrados na busca atual
        (não o histórico completo do banco)."""
        self.limpar_tabela()
        data_hora = datetime.now().strftime("%d/%m/%Y %H:%M")
        for item in resultados:
            preco_fmt = f"R$ {item['preco']:.2f}" if item["preco"] > 0 else "N/D"
            self.tree.insert("", tk.END, values=(data_hora, termo, item["titulo"], preco_fmt, item["link"]))
 
    def carregar_historico_banco(self):
        """Carrega todos os dados gravados no banco SQLite para a tabela."""
        self.limpar_tabela()
        registros = obter_historico_completo()
 
        if not registros:
            self.atualizar_status("O banco de dados está vazio.")
            messagebox.showinfo("Informação", "Nenhum histórico encontrado no banco de dados.")
            return
 
        for reg in registros:
            data, termo, titulo, preco, link = reg
            preco_fmt = f"R$ {preco:.2f}" if preco > 0 else "N/D"
            self.tree.insert("", tk.END, values=(data, termo, titulo, preco_fmt, link))
 
        self.atualizar_status(f"Carregados {len(registros)} registros do banco 'historico.db'.")
 
    def abrir_arquivo_excel(self):
        """Abre uma caixa de diálogo para carregar uma planilha .xlsx externa e exibir na tela."""
        caminho = filedialog.askopenfilename(
            title="Selecione um arquivo Excel",
            filetypes=[("Arquivos Excel", "*.xlsx *.xls")]
        )
        if not caminho:
            return
        self.carregar_arquivo(caminho)
 
    def carregar_arquivo(self, caminho: str):
        """Lê um arquivo exportado (.xlsx ou .json) e exibe os registros na tabela.
        Usado tanto pelo 'Abrir e Ler Planilha Excel' quanto pelo 'Ver Exportações'."""
        try:
            if caminho.lower().endswith(".json"):
                with open(caminho, "r", encoding="utf-8") as f:
                    registros = json.load(f)
            else:
                df = pd.read_excel(caminho)
                registros = df.to_dict(orient="records")
 
            self.limpar_tabela()
            for row in registros:
                # Tenta ler as colunas de acordo com os nomes padrões exportados
                data = row.get("Data/Hora", "-")
                termo = row.get("Termo Pesquisado", row.get("Termo", "-"))
                titulo = row.get("Produto", row.get("titulo", "-"))
                preco = row.get("Preço (R$)", row.get("preco", 0.0))
                link = row.get("Link", row.get("link", "-"))
 
                preco_fmt = f"R$ {float(preco):.2f}" if isinstance(preco, (int, float)) and preco > 0 else str(preco)
                self.tree.insert("", tk.END, values=(data, termo, titulo, preco_fmt, link))
 
            self.atualizar_status(f"Exibindo dados do arquivo: {os.path.basename(caminho)}")
            messagebox.showinfo("Sucesso", f"Arquivo '{os.path.basename(caminho)}' carregado com sucesso!")
        except Exception as e:
            messagebox.showerror("Erro ao ler arquivo", f"Não foi possível ler o arquivo:\n{str(e)}")
 
    def exportar_excel(self):
        df = obter_df_historico()
        if df.empty:
            messagebox.showwarning("Aviso", "O banco de dados não possui registros para exportar.")
            return
 
        nome_arquivo = f"historico_exportado_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        df.to_excel(nome_arquivo, index=False)
        messagebox.showinfo("Exportado!", f"Histórico exportado com sucesso!\nArquivo gerado: {nome_arquivo}")
 
    def exportar_json(self):
        df = obter_df_historico()
        if df.empty:
            messagebox.showwarning("Aviso", "O banco de dados não possui registros para exportar.")
            return
 
        nome_arquivo = f"historico_exportado_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        registros = df.to_dict(orient="records")
        with open(nome_arquivo, "w", encoding="utf-8") as f:
            json.dump(registros, f, ensure_ascii=False, indent=2)
        messagebox.showinfo("Exportado!", f"Histórico exportado com sucesso!\nArquivo gerado: {nome_arquivo}")
 
    def ver_exportacoes(self):
        """Lista os arquivos já exportados (Excel e JSON) nesta pasta e
        permite carregar um deles na tabela, sem precisar navegar
        manualmente pelo explorador de arquivos."""
        arquivos = sorted(
            [f for f in os.listdir(".") if f.startswith("historico_exportado_") and f.lower().endswith((".xlsx", ".json"))],
            reverse=True  # mais recentes primeiro, já que o nome tem timestamp
        )
 
        janela = tk.Toplevel(self.root)
        janela.title("Exportações Salvas")
        janela.geometry("480x340")
        janela.config(bg="#f4f6f9")
 
        tk.Label(
            janela, text="Arquivos exportados nesta pasta:",
            font=("Arial", 11, "bold"), bg="#f4f6f9"
        ).pack(pady=8)
 
        lista = tk.Listbox(janela, font=("Arial", 10), width=58, height=12)
        lista.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
 
        if not arquivos:
            lista.insert(tk.END, "Nenhuma exportação encontrada ainda.")
        else:
            for arq in arquivos:
                lista.insert(tk.END, arq)
 
        def carregar_selecionado():
            selecao = lista.curselection()
            if not selecao or not arquivos:
                messagebox.showwarning("Aviso", "Selecione um arquivo da lista.")
                return
            nome_arquivo = lista.get(selecao[0])
            self.carregar_arquivo(nome_arquivo)
            janela.destroy()
 
        btn_carregar = tk.Button(
            janela, text="📥 Carregar Selecionado", font=("Arial", 10, "bold"),
            bg="#007bff", fg="white", padx=10, command=carregar_selecionado
        )
        btn_carregar.pack(pady=10)
 
if __name__ == "__main__":
    root = tk.Tk()
    app = AppAutomação(root)
    root.mainloop()