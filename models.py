# laticinios_armazem/models.py

from datetime import datetime, date
from typing import Optional, List, Dict, Any

# Bancos de dados simulados
db_usuarios: Dict[str, Dict[str, Any]] = {}
db_areas_armazem: Dict[str, Dict[str, Any]] = {}
db_vendas_registradas: List[Dict[str, Any]] = []
db_produtos_catalogo: Dict[str, Dict[str, str]] = {}

class Usuario:
    def __init__(self, username: str, funcao: str, nome: str):
        self.username = username
        self.funcao = funcao
        self.nome = nome

    @staticmethod
    def verificar_senha(username: str, senha: str) -> Optional['Usuario']:
        user_data = db_usuarios.get(username)
        if user_data and user_data['senha'] == senha:
            return Usuario(username, user_data['funcao'], user_data['nome'])
        return None

    def tem_permissao(self, permissao: str) -> bool:
        permissoes_por_funcao = {
            'gerente': ['visualizar_armazem', 'detalhes_area', 'gerente', 'registrar_venda'],
            'operador': ['visualizar_armazem', 'detalhes_area', 'registrar_venda']
        }
        return permissao in permissoes_por_funcao.get(self.funcao, [])

class ProdutoLacteo:
    def __init__(self, id_catalogo_produto: str, nome: str, quantidade: int, data_validade_str: str, lote: str):
        self.id_catalogo_produto = id_catalogo_produto
        self.nome = nome
        self.quantidade = quantidade
        self.data_validade = datetime.strptime(data_validade_str, '%Y-%m-%d').date()
        self.lote = lote

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id_catalogo_produto': self.id_catalogo_produto,
            'nome': self.nome,
            'quantidade': self.quantidade,
            'data_validade': self.data_validade.strftime('%Y-%m-%d'),
            'lote': self.lote
        }

class AreaArmazem:
    def __init__(self, id_area: str, nome: str, tipo_armazenamento: str):
        self.id_area = id_area
        self.nome = nome
        self.tipo_armazenamento = tipo_armazenamento
        if id_area not in db_areas_armazem:
            db_areas_armazem[id_area] = {'nome': nome, 'tipo_armazenamento': tipo_armazenamento, 'produtos': []}

    @staticmethod
    def buscar_por_id(id_area: str) -> Optional['AreaArmazem']:
        area_data = db_areas_armazem.get(id_area)
        if area_data:
            return AreaArmazem(id_area, area_data['nome'], area_data['tipo_armazenamento'])
        return None

    @staticmethod
    def listar_todas() -> List['AreaArmazem']:
        return [AreaArmazem(id_area, data['nome'], data['tipo_armazenamento'])
                for id_area, data in db_areas_armazem.items()]

    def adicionar_produto(self, produto: ProdutoLacteo) -> None:
        area_data = db_areas_armazem[self.id_area]
        for existing_product in area_data['produtos']:
            if (existing_product.id_catalogo_produto == produto.id_catalogo_produto and
                existing_product.lote == produto.lote):
                existing_product.quantidade += produto.quantidade
                return
        area_data['produtos'].append(produto)

    def listar_produtos(self) -> List[ProdutoLacteo]:
        return db_areas_armazem[self.id_area]['produtos']

    def remover_produto(self, id_catalogo_produto: str, lote: str, quantidade: int) -> bool:
        area_data = db_areas_armazem[self.id_area]
        for i, produto in enumerate(area_data['produtos']):
            if produto.id_catalogo_produto == id_catalogo_produto and produto.lote == lote:
                if produto.quantidade < quantidade:
                    return False
                produto.quantidade -= quantidade
                if produto.quantidade == 0:
                    area_data['produtos'].pop(i)
                return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id_area': self.id_area,
            'nome': self.nome,
            'tipo_armazenamento': self.tipo_armazenamento,
            'produtos': [p.to_dict() for p in self.listar_produtos()]
        }

class Venda:
    def __init__(self, id_catalogo_produto: str, nome: str, lote: str, data_validade_produto: str,
                 quantidade_vendida: int, destino: str, area_origem_id: str, usuario_responsavel: str):
        self.id_catalogo_produto = id_catalogo_produto
        self.nome = nome
        self.lote = lote
        self.data_validade_produto = data_validade_produto
        self.quantidade_vendida = quantidade_vendida
        self.destino = destino
        self.area_origem_id = area_origem_id
        self.usuario_responsavel = usuario_responsavel
        self.data_hora = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id_catalogo_produto': self.id_catalogo_produto,
            'nome': self.nome,
            'lote': self.lote,
            'data_validade_produto': self.data_validade_produto,
            'quantidade_vendida': self.quantidade_vendida,
            'destino': self.destino,
            'area_origem_id': self.area_origem_id,
            'usuario_responsavel': self.usuario_responsavel,
            'data_hora': self.data_hora.isoformat()
        }

    @staticmethod
    def registrar(venda: 'Venda') -> None:
        db_vendas_registradas.append(venda)

    @staticmethod
    def listar_todas() -> List['Venda']:
        return db_vendas_registradas

def get_produto_catalogo_por_id(id_produto: str) -> Optional[Dict[str, str]]:
    return db_produtos_catalogo.get(id_produto)

def popular_dados_iniciais() -> None:
    db_usuarios.update({
        'operador1': {'senha': 'senha123', 'funcao': 'operador', 'nome': 'João Silva'},
        'gerente1': {'senha': 'senhaforte', 'funcao': 'gerente', 'nome': 'Maria Oliveira'}
    })

    db_produtos_catalogo.update({
        'LEITE001': {'nome': 'Leite Integral UHT 1L'},
        'IOG002': {'nome': 'Iogurte Natural Copo 170g'},
        'QUE003': {'nome': 'Queijo Minas Frescal 500g'},
        'MAN004': {'nome': 'Manteiga com Sal 200g'}
    })

    db_areas_armazem.update({
        'A1': {
            'nome': 'Refrigerados Rápidos',
            'tipo_armazenamento': 'refrigerado',
            'produtos': [
                ProdutoLacteo('LEITE001', 'Leite Integral UHT 1L', 100, '2025-05-20', 'LOTE2025A'),
                ProdutoLacteo('IOG002', 'Iogurte Natural Copo 170g', 50, '2025-05-15', 'LOTE2025B'),
                ProdutoLacteo('IOG002', 'Iogurte Natural Copo 170g', 30, '2025-05-10', 'LOTE2025C')
            ]
        },
        'B2': {
            'nome': 'Congelados Profundos',
            'tipo_armazenamento': 'congelado',
            'produtos': [
                ProdutoLacteo('QUE003', 'Queijo Minas Frescal 500g', 70, '2025-05-19', 'LOTE2025D'),
                ProdutoLacteo('MAN004', 'Manteiga com Sal 200g', 40, '2025-07-08', 'LOTE2025E')
            ]
        },
        'C3': {
            'nome': 'Estoque Seco',
            'tipo_armazenamento': 'seco',
            'produtos': []
        }
    })