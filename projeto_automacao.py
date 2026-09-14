import requests
from bs4 import BeautifulSoup
import re
import sys
 
 
# Cabeçalhos para simular um navegador real e reduzir chance de bloqueio.
# Sites como o Mercado Livre podem recusar requisições sem um User-Agent válido.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}
 
MAX_RESULTADOS = 10
 
 
def montar_url_busca(produto: str) -> str:
    """
    Monta a URL de busca do Mercado Livre a partir do termo pesquisado.
    Espaços viram '-' e caracteres especiais são tratados de forma simples.
    Exemplo: "notebook gamer" -> https://lista.mercadolivre.com.br/notebook-gamer
    """
    termo = produto.strip().lower()
    termo = re.sub(r"\s+", "-", termo)
    return f"https://lista.mercadolivre.com.br/{termo}"
 
 
# ---------------------------------------------------------------------------
# MÉTODO PRINCIPAL: API pública de busca do Mercado Livre
# ---------------------------------------------------------------------------
# O Mercado Livre bloqueia scraping direto de HTML nas páginas de busca
# (isso está declarado no robots.txt do site). Por isso, o método principal
# deste script usa a API pública oficial de busca, que devolve os dados
# já estruturados em JSON — sem depender de classes CSS que mudam com
# o tempo. Isso ainda conta como automação: estamos automatizando a
# consulta e o processamento dos dados via requisição HTTP.
API_BUSCA_URL = "https://api.mercadolibre.com/sites/MLB/search"
 
 
def buscar_via_api(termo: str, limite: int = MAX_RESULTADOS, debug: bool = False) -> list[dict]:
    """
    Busca produtos usando a API pública do Mercado Livre e retorna
    uma lista de dicts no mesmo formato usado por extrair_produtos():
    {"nome": ..., "preco": ..., "link": ...}
    """
    params = {"q": termo, "limit": limite}
    resposta = requests.get(API_BUSCA_URL, headers=HEADERS, params=params, timeout=10)
 
    if debug:
        print(f"[DEBUG] URL acessada: {resposta.url}")
        print(f"[DEBUG] Status code: {resposta.status_code}")
 
    resposta.raise_for_status()
    dados = resposta.json()
 
    produtos = []
    for item in dados.get("results", [])[:limite]:
        produtos.append({
            "nome": item.get("title", "Nome não encontrado"),
            "preco": f"R$ {item.get('price', 'não encontrado')}",
            "link": item.get("permalink", "Link não encontrado"),
        })
    return produtos
 
 
def buscar_html(url: str, debug: bool = False) -> str:
    """
    Faz a requisição HTTP para a URL de busca e retorna o HTML da página.
    Lança uma exceção clara se algo der errado (timeout, bloqueio, etc).
 
    Se debug=True, imprime o status code e salva o HTML recebido em
    'debug_response.html', para inspecionarmos o que o site realmente
    devolveu (útil quando o site bloqueia ou muda a estrutura).
    """
    resposta = requests.get(url, headers=HEADERS, timeout=10)
 
    if debug:
        print(f"[DEBUG] URL acessada: {url}")
        print(f"[DEBUG] Status code: {resposta.status_code}")
        print(f"[DEBUG] Tamanho do HTML recebido: {len(resposta.text)} caracteres")
        with open("debug_response.html", "w", encoding="utf-8") as f:
            f.write(resposta.text)
        print("[DEBUG] HTML salvo em 'debug_response.html' para inspeção.")
 
    resposta.raise_for_status()  # dispara erro se status != 200
    return resposta.text
 
 
def extrair_produtos(html: str, limite: int = MAX_RESULTADOS) -> list[dict]:
    """
    Recebe o HTML da página de busca e extrai nome, preço e link
    de cada produto encontrado, até o limite definido.
 
    OBS: O Mercado Livre pode alterar a estrutura do HTML (nomes de classes)
    com o tempo. Se o scraper parar de encontrar resultados, o primeiro
    passo é inspecionar o HTML atual (botão direito -> Inspecionar no
    navegador) e ajustar os seletores abaixo.
    """
    soup = BeautifulSoup(html, "html.parser")
    produtos = []
 
    # Cada card de produto normalmente fica dentro de um <li> ou <div>
    # com uma classe que contém "ui-search-layout__item" ou similar.
    cards = soup.select("li.ui-search-layout__item, div.ui-search-result__wrapper")
 
    for card in cards:
        if len(produtos) >= limite:
            break
 
        # --- Nome do produto ---
        nome_tag = card.select_one("h2.ui-search-item__title, a.poly-component__title")
        nome = nome_tag.get_text(strip=True) if nome_tag else None
 
        # --- Link do produto ---
        link_tag = card.select_one("a.ui-search-link, a.poly-component__title")
        link = link_tag.get("href") if link_tag else None
 
        # --- Preço do produto ---
        preco_tag = card.select_one("span.andes-money-amount__fraction")
        preco = preco_tag.get_text(strip=True) if preco_tag else None
 
        # Só adiciona se conseguimos extrair pelo menos nome e link.
        # Isso evita "produtos fantasmas" causados por anúncios ou
        # elementos de layout que não são produtos de verdade.
        if nome and link:
            produtos.append({
                "nome": nome,
                "preco": f"R$ {preco}" if preco else "Preço não encontrado",
                "link": link,
            })
 
    return produtos
 
 
def exibir_resultados(produtos: list[dict], termo: str) -> None:
    """Imprime a mini lista de resultados formatada no terminal."""
    if not produtos:
        print(f"\nNenhum produto encontrado para '{termo}'.")
        print("Possíveis causas: site bloqueou a requisição, termo sem resultados,")
        print("ou a estrutura do HTML mudou (veja os comentários em extrair_produtos).")
        return
 
    print(f"\nResultados para '{termo}' ({len(produtos)} produtos):\n")
    print("-" * 70)
    for i, p in enumerate(produtos, start=1):
        print(f"{i}. {p['nome']}")
        print(f"   Preço: {p['preco']}")
        print(f"   Link:  {p['link']}")
        print("-" * 70)
 
 
def buscar_produto(termo: str, debug: bool = False) -> list[dict]:
    """
    Função principal de alto nível: recebe o termo de busca e devolve
    a lista de produtos já processada.
 
    Estratégia:
    1. Tenta primeiro a API pública do Mercado Livre (mais estável).
    2. Se a API falhar por qualquer motivo, tenta o scraping de HTML
       como plano B (útil para o relatório, mostrando as duas técnicas).
    """
    try:
        if debug:
            print("[DEBUG] Tentando via API pública...")
        produtos = buscar_via_api(termo, debug=debug)
        if produtos:
            return produtos
        if debug:
            print("[DEBUG] API não retornou produtos, tentando scraping de HTML...")
    except requests.exceptions.RequestException as e:
        if debug:
            print(f"[DEBUG] API falhou ({e}), tentando scraping de HTML...")
 
    url = montar_url_busca(termo)
    html = buscar_html(url, debug=debug)
    return extrair_produtos(html)
 
 
def main():
    print("=== Buscador de Produtos - Mercado Livre ===")
    termo = input("Digite o produto que deseja pesquisar: ").strip()
 
    if not termo:
        print("Você precisa digitar um termo de busca.")
        sys.exit(1)
 
    try:
        produtos = buscar_produto(termo, debug=True)
        exibir_resultados(produtos, termo)
    except requests.exceptions.Timeout:
        print("Erro: o site demorou demais para responder (timeout).")
    except requests.exceptions.HTTPError as e:
        print(f"Erro HTTP ao acessar o Mercado Livre: {e}")
    except requests.exceptions.RequestException as e:
        print(f"Erro de conexão: {e}")
 
 
if __name__ == "__main__":
    main()