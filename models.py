# laticinios_armazem/models.py

from datetime import datetime, timedelta

# --- Dados em Memória (Simulação de Banco de Dados) ---
# Em um sistema real, isso viria de um banco de dados.
db_usuarios = {
    "operador1": {"senha": "senha123", "funcao": "operador", "nome": "João Operador"},
    "gerente1": {"senha": "senhaforte", "funcao": "gerente", "nome": "Maria Gerente"}
}

db_areas_armazem = {
    "A1": {"nome": "Área A1 - Refrigerados Rápidos", "produtos": []},
    "B2": {"nome": "Área B2 - Congelados Profundos", "produtos": []},
    "C3": {"nome": "Área C3 - Secos Validade Longa", "produtos": []},
}

db_vendas_registradas = []
db_produtos_catalogo = [ # Catálogo de produtos que podem existir
    {"id": "LEITE001", "nome": "Leite Integral UHT 1L"},
    {"id": "IOG002", "nome": "Iogurte Natural Copo 170g"},
    {"id": "QUE003", "nome": "Queijo Minas Frescal 500g"},
    {"id": "MAN004", "nome": "Manteiga com Sal 200g"}
]

# --- Classes do Modelo ---

class ProdutoLacteo:
    def __init__(self, id_produto_catalogo: str, nome: str, quantidade: int, data_validade: str, lote: str):
        """
        Representa um lote específico de um produto lácteo no armazém.
        data_validade deve estar no formato 'YYYY-MM-DD'.
        """
        self.id_produto_catalogo = id_produto_catalogo # ID do tipo de produto (ex: LEITE001)
        self.nome = nome
        self.quantidade = quantidade
        try:
            self.data_validade = datetime.strptime(data_validade, '%Y-%m-%d').date()
        except ValueError:
            raise ValueError("Formato de data_validade inválido. Use YYYY-MM-DD.")
        self.lote = lote

    def __repr__(self):
        return f"<ProdutoLacteo {self.nome} (Lote: {self.lote}, Qtd: {self.quantidade}, Val: {self.data_validade})>"

    def to_dict(self):
        return {
            "id_produto_catalogo": self.id_produto_catalogo,
            "nome": self.nome,
            "quantidade": self.quantidade,
            "data_validade": self.data_validade.strftime('%Y-%m-%d'),
            "lote": self.lote
        }

class AreaArmazem:
    def __init__(self, id_area: str, nome: str):
        self.id_area = id_area
        self.nome = nome
        # Usaremos os produtos diretamente de db_areas_armazem para simplificar
        # self.produtos = [] # Lista de objetos ProdutoLacteo

    def adicionar_produto(self, produto: ProdutoLacteo):
        """Adiciona um produto à área. Se já existir um produto com mesmo ID e lote, atualiza a quantidade."""
        encontrado = False
        for p_existente in db_areas_armazem[self.id_area]["produtos"]:
            if p_existente.id_produto_catalogo == produto.id_produto_catalogo and p_existente.lote == produto.lote and p_existente.data_validade == produto.data_validade:
                p_existente.quantidade += produto.quantidade
                encontrado = True
                break
        if not encontrado:
            db_areas_armazem[self.id_area]["produtos"].append(produto)

    def remover_produto(self, id_produto_catalogo: str, lote: str, quantidade_remover: int) -> bool:
        """Remove uma quantidade de um produto específico da área."""
        for produto in db_areas_armazem[self.id_area]["produtos"]:
            if produto.id_produto_catalogo == id_produto_catalogo and produto.lote == lote:
                if produto.quantidade >= quantidade_remover:
                    produto.quantidade -= quantidade_remover
                    if produto.quantidade == 0:
                        # Remove o produto da lista se a quantidade zerar
                        db_areas_armazem[self.id_area]["produtos"].remove(produto)
                    return True
                else:
                    # Quantidade insuficiente
                    return False
        return False # Produto não encontrado

    def listar_produtos(self) -> list:
        """Retorna a lista de produtos na área."""
        return db_areas_armazem[self.id_area]["produtos"]

    def to_dict(self):
        return {
            "id_area": self.id_area,
            "nome": self.nome,
            "produtos": [p.to_dict() for p in self.listar_produtos()]
        }

class Venda:
    def __init__(self, id_produto_catalogo: str, nome_produto: str, lote: str, quantidade_vendida: int, destino: str, area_origem_id: str, data_hora: datetime = None):
        self.id_produto_catalogo = id_produto_catalogo
        self.nome_produto = nome_produto
        self.lote = lote
        self.quantidade_vendida = quantidade_vendida
        self.destino = destino
        self.area_origem_id = area_origem_id
        self.data_hora = data_hora or datetime.now()

    def __repr__(self):
        return f"<Venda {self.quantidade_vendida}x {self.nome_produto} (Lote: {self.lote}) para {self.destino} em {self.data_hora}>"

    def to_dict(self):
        return {
            "id_produto_catalogo": self.id_produto_catalogo,
            "nome_produto": self.nome_produto,
            "lote": self.lote,
            "quantidade_vendida": self.quantidade_vendida,
            "destino": self.destino,
            "area_origem_id": self.area_origem_id,
            "data_hora": self.data_hora.strftime('%Y-%m-%d %H:%M:%S')
        }

class Usuario:
    def __init__(self, username: str, funcao: str, nome: str):
        self.username = username
        self.funcao = funcao # 'operador', 'gerente'
        self.nome = nome

    @staticmethod
    def verificar_senha(username, senha_fornecida):
        user_data = db_usuarios.get(username)
        if user_data and user_data["senha"] == senha_fornecida:
            return Usuario(username, user_data["funcao"], user_data["nome"])
        return None

    def tem_permissao(self, permissao_requerida: str) -> bool:
        """Verifica se o usuário tem a permissão necessária.
        Ex: 'gerenciar_estoque', 'ver_relatorios_completos'
        """
        if self.funcao == 'gerente':
            return True # Gerente tem todas as permissões neste modelo simples
        elif self.funcao == 'operador':
            return permissao_requerida in ['visualizar_armazem', 'registrar_venda', 'ver_estoque_area']
        return False

# --- Funções Auxiliares do Modelo (interação com 'db_') ---

def get_area_por_id(id_area: str) -> AreaArmazem | None:
    dados_area = db_areas_armazem.get(id_area)
    if dados_area:
        return AreaArmazem(id_area, dados_area["nome"])
    return None

def listar_todas_as_areas() -> list:
    return [AreaArmazem(id_a, dados['nome']) for id_a, dados in db_areas_armazem.items()]

def registrar_venda_no_db(venda: Venda):
    db_vendas_registradas.append(venda)

def get_produto_catalogo_por_id(id_produto_catalogo: str) -> dict | None:
    for prod in db_produtos_catalogo:
        if prod["id"] == id_produto_catalogo:
            return prod
    return None

def popular_dados_iniciais():
    """Popula o armazém com alguns produtos para demonstração."""
    if not any(area_data["produtos"] for area_data in db_areas_armazem.values()): # Popula apenas se estiver vazio
        area_a1 = get_area_por_id("A1")
        area_b2 = get_area_por_id("B2")

        if area_a1:
            area_a1.adicionar_produto(ProdutoLacteo("LEITE001", "Leite Integral UHT 1L", 100, (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d'), "LOTE2025A"))
            area_a1.adicionar_produto(ProdutoLacteo("IOG002", "Iogurte Natural Copo 170g", 50, (datetime.now() + timedelta(days=15)).strftime('%Y-%m-%d'), "LOTE2025B"))
            area_a1.adicionar_produto(ProdutoLacteo("IOG002", "Iogurte Natural Copo 170g", 30, (datetime.now() + timedelta(days=5)).strftime('%Y-%m-%d'), "LOTE2025C")) # Lote próximo da validade
        if area_b2:
            area_b2.adicionar_produto(ProdutoLacteo("QUE003", "Queijo Minas Frescal 500g", 70, (datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d'), "LOTE2025D"))
            area_b2.adicionar_produto(ProdutoLacteo("MAN004", "Manteiga com Sal 200g", 40, (datetime.now() + timedelta(days=60)).strftime('%Y-%m-%d'), "LOTE2025E"))
        print("Dados iniciais populados.")

# Chama a função para popular os dados quando o módulo é carregado (para desenvolvimento)
popular_dados_iniciais()