# laticinios_armazem/models.py

import sqlite3
from datetime import datetime, date
from typing import Optional, List, Dict, Any

# Define o caminho para o arquivo do banco de dados SQLite.
DATABASE_PATH = 'data/laticinios.db'

def get_db_connection() -> sqlite3.Connection:
    """Estabelece e retorna uma conexão com o banco de dados SQLite.

    A conexão é configurada para retornar linhas como objetos sqlite3.Row,
    o que permite o acesso às colunas por nome.

    Returns:
        sqlite3.Connection: Objeto de conexão com o banco de dados.
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Permite acessar colunas por nome
    return conn

def init_db() -> None:
    """Inicializa o banco de dados criando as tabelas a partir do schema.sql.

    Lê o arquivo schema.sql e executa os comandos SQL para criar a estrutura
    do banco de dados, caso ela ainda não exista.
    """
    # É importante que o schema.sql esteja no mesmo diretório ou que o caminho seja ajustado.
    with open('schema.sql', 'r') as f:
        schema = f.read()
    conn = get_db_connection()
    conn.executescript(schema)  # Executa múltiplos comandos SQL do schema
    conn.commit()  # Salva as alterações no banco de dados
    conn.close()   # Fecha a conexão

class Usuario:
    """Representa um usuário do sistema.

    Atributos:
        username (str): Nome de usuário único.
        funcao (str): Função do usuário no sistema (ex: 'gerente', 'operador').
        nome (str): Nome completo do usuário.
    """
    def __init__(self, username: str, funcao: str, nome: str):
        self.username = username
        self.funcao = funcao
        self.nome = nome

    @staticmethod
    def verificar_senha(username: str, senha: str) -> Optional['Usuario']:
        """Verifica se o nome de usuário e a senha correspondem a um usuário no banco de dados.

        Args:
            username (str): O nome de usuário a ser verificado.
            senha (str): A senha a ser verificada (em texto plano, conforme o schema atual).

        Returns:
            Optional[Usuario]: Um objeto Usuario se as credenciais forem válidas, None caso contrário.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        # ATENÇÃO: Armazenar senhas em texto plano é uma falha de segurança grave.
        # Em um sistema de produção, use hashing de senhas (ex: Werkzeug, passlib).
        cursor.execute('SELECT * FROM usuarios WHERE username = ? AND senha = ?', (username, senha))
        user_data = cursor.fetchone()
        conn.close()
        if user_data:
            return Usuario(user_data['username'], user_data['funcao'], user_data['nome'])
        return None

    def tem_permissao(self, permissao: str) -> bool:
        """Verifica se o usuário tem uma determinada permissão com base em sua função.

        Args:
            permissao (str): A string da permissão a ser verificada (ex: 'visualizar_armazem').

        Returns:
            bool: True se o usuário tiver a permissão, False caso contrário.
        """
        permissoes_por_funcao = {
            'gerente': ['visualizar_armazem', 'detalhes_area', 'gerente', 'registrar_venda'],
            'operador': ['visualizar_armazem', 'detalhes_area', 'registrar_venda']
            # Adicione mais funções e permissões conforme necessário
        }
        return permissao in permissoes_por_funcao.get(self.funcao, [])

class ProdutoLacteo:
    """Representa um produto lácteo específico em estoque.

    Atributos:
        id_catalogo_produto (str): Identificador do produto no catálogo.
        nome (str): Nome do produto.
        quantidade (int): Quantidade do produto em estoque.
        data_validade (date): Data de validade do produto.
        lote (str): Lote de fabricação do produto.
    """
    def __init__(self, id_catalogo_produto: str, nome: str, quantidade: int, data_validade_str: str, lote: str):
        self.id_catalogo_produto = id_catalogo_produto
        self.nome = nome
        self.quantidade = quantidade
        # Converte a string de data para um objeto date
        try:
            self.data_validade = datetime.strptime(data_validade_str, '%Y-%m-%d').date()
        except ValueError:
            # Tratar erro de formato de data, se necessário, ou levantar exceção
            raise ValueError(f"Formato de data inválido para '{data_validade_str}'. Use AAAA-MM-DD.")
        self.lote = lote

    def to_dict(self) -> Dict[str, Any]:
        """Converte o objeto ProdutoLacteo para um dicionário.

        Returns:
            Dict[str, Any]: Representação do produto em formato de dicionário.
        """
        return {
            'id_catalogo_produto': self.id_catalogo_produto,
            'nome': self.nome,
            'quantidade': self.quantidade,
            'data_validade': self.data_validade.strftime('%Y-%m-%d'), # Converte date para string no formato AAAA-MM-DD
            'lote': self.lote
        }

class AreaArmazem:
    """Representa uma área de armazenamento no sistema.

    Atributos:
        id_area (str): Identificador único da área de armazenamento.
        nome (str): Nome descritivo da área.
        tipo_armazenamento (str): Tipo de armazenamento (ex: 'refrigerado', 'seco', 'congelado').
    """
    def __init__(self, id_area: str, nome: str, tipo_armazenamento: str):
        self.id_area = id_area
        self.nome = nome
        self.tipo_armazenamento = tipo_armazenamento

    @staticmethod
    def buscar_por_id(id_area: str) -> Optional['AreaArmazem']:
        """Busca uma área de armazenamento pelo seu ID no banco de dados.

        Args:
            id_area (str): O ID da área a ser buscada.

        Returns:
            Optional[AreaArmazem]: Um objeto AreaArmazem se encontrada, None caso contrário.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        # CORREÇÃO: Nome da tabela é 'areas_armazem'
        cursor.execute('SELECT * FROM areas_armazem WHERE id_area = ?', (id_area,))
        area_data = cursor.fetchone()
        conn.close()
        if area_data:
            return AreaArmazem(area_data['id_area'], area_data['nome'], area_data['tipo_armazenamento'])
        return None

    @staticmethod
    def listar_todas() -> List['AreaArmazem']:
        """Lista todas as áreas de armazenamento cadastradas no banco de dados.

        Returns:
            List[AreaArmazem]: Uma lista de objetos AreaArmazem.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        # CORREÇÃO: Nome da tabela é 'areas_armazem'
        cursor.execute('SELECT * FROM areas_armazem ORDER BY nome') # Ordena por nome para melhor visualização
        areas_data = cursor.fetchall()
        conn.close()
        return [AreaArmazem(row['id_area'], row['nome'], row['tipo_armazenamento']) for row in areas_data]

    def adicionar_produto(self, produto: ProdutoLacteo) -> None:
        """Adiciona um produto (ou atualiza sua quantidade) a esta área de armazenamento no banco de dados.

        Se um produto com o mesmo id_catalogo_produto e lote já existir na área,
        sua quantidade é somada. Caso contrário, um novo registro é inserido.

        Args:
            produto (ProdutoLacteo): O objeto ProdutoLacteo a ser adicionado.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        # Verifica se o produto já existe na tabela 'produtos_areas'
        cursor.execute('''
            SELECT quantidade FROM produtos_areas
            WHERE id_area = ? AND id_catalogo_produto = ? AND lote = ?
        ''', (self.id_area, produto.id_catalogo_produto, produto.lote))
        existing_product = cursor.fetchone()

        if existing_product:
            # Produto já existe, atualiza a quantidade
            new_quantidade = existing_product['quantidade'] + produto.quantidade
            cursor.execute('''
                UPDATE produtos_areas
                SET quantidade = ?
                WHERE id_area = ? AND id_catalogo_produto = ? AND lote = ?
            ''', (new_quantidade, self.id_area, produto.id_catalogo_produto, produto.lote))
        else:
            # Produto não existe, insere novo registro na tabela 'produtos_areas'
            cursor.execute('''
                INSERT INTO produtos_areas (id_area, id_catalogo_produto, nome, quantidade, data_validade, lote)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (self.id_area, produto.id_catalogo_produto, produto.nome, produto.quantidade,
                  produto.data_validade.strftime('%Y-%m-%d'), produto.lote))
        conn.commit()
        conn.close()

    def listar_produtos(self) -> List[ProdutoLacteo]:
        """Lista todos os produtos contidos nesta área de armazenamento, ordenados por data de validade.

        Returns:
            List[ProdutoLacteo]: Uma lista de objetos ProdutoLacteo.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        # Busca produtos na tabela 'produtos_areas'
        cursor.execute('''
            SELECT id_catalogo_produto, nome, quantidade, data_validade, lote
            FROM produtos_areas
            WHERE id_area = ?
            ORDER BY data_validade ASC  -- Ordena por data de validade, mais próximos primeiro
        ''', (self.id_area,))
        produtos_data = cursor.fetchall()
        conn.close()
        return [ProdutoLacteo(row['id_catalogo_produto'], row['nome'], row['quantidade'],
                                  row['data_validade'], row['lote']) for row in produtos_data]

    def remover_produto(self, id_catalogo_produto: str, lote: str, quantidade: int) -> bool:
        """Remove uma certa quantidade de um produto específico (identificado por ID do catálogo e lote)
        desta área de armazenamento no banco de dados.

        Se a quantidade a ser removida for igual ou maior que a existente, o produto é totalmente removido.
        Caso contrário, apenas a quantidade é decrementada.

        Args:
            id_catalogo_produto (str): ID do produto no catálogo.
            lote (str): Lote do produto.
            quantidade (int): Quantidade a ser removida.

        Returns:
            bool: True se a remoção for bem-sucedida, False caso contrário (produto não encontrado ou quantidade insuficiente).
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        # Verifica o produto na tabela 'produtos_areas'
        cursor.execute('''
            SELECT quantidade FROM produtos_areas
            WHERE id_area = ? AND id_catalogo_produto = ? AND lote = ?
        ''', (self.id_area, id_catalogo_produto, lote))
        existing_product = cursor.fetchone()

        if not existing_product or existing_product['quantidade'] < quantidade:
            # Produto não encontrado ou quantidade em estoque é insuficiente
            conn.close()
            return False

        new_quantidade = existing_product['quantidade'] - quantidade
        if new_quantidade == 0:
            # Remove o produto completamente da tabela 'produtos_areas' se a quantidade zerar
            cursor.execute('''
                DELETE FROM produtos_areas
                WHERE id_area = ? AND id_catalogo_produto = ? AND lote = ?
            ''', (self.id_area, id_catalogo_produto, lote))
        else:
            # Atualiza a quantidade do produto na tabela 'produtos_areas'
            cursor.execute('''
                UPDATE produtos_areas
                SET quantidade = ?
                WHERE id_area = ? AND id_catalogo_produto = ? AND lote = ?
            ''', (new_quantidade, self.id_area, id_catalogo_produto, lote))
        conn.commit()
        conn.close()
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Converte o objeto AreaArmazem e seus produtos para um dicionário.

        Returns:
            Dict[str, Any]: Representação da área e seus produtos em formato de dicionário.
        """
        return {
            'id_area': self.id_area,
            'nome': self.nome,
            'tipo_armazenamento': self.tipo_armazenamento,
            'produtos': [p.to_dict() for p in self.listar_produtos()] # Lista os produtos da área
        }

class Venda:
    """Representa uma transação de venda de um produto.

    Atributos:
        id_catalogo_produto (str): ID do produto vendido (do catálogo).
        nome (str): Nome do produto vendido.
        lote (str): Lote do produto vendido.
        data_validade_produto (str): Data de validade do produto no momento da venda.
        quantidade_vendida (int): Quantidade do produto que foi vendida.
        destino (str): Destino da venda (cliente, outra área, etc.).
        area_origem_id (str): ID da área de onde o produto foi vendido.
        usuario_responsavel (str): Username do usuário que registrou a venda.
        data_hora (datetime): Data e hora em que a venda foi registrada.
    """
    def __init__(self, id_catalogo_produto: str, nome: str, lote: str, data_validade_produto: str,
                 quantidade_vendida: int, destino: str, area_origem_id: str, usuario_responsavel: str):
        self.id_catalogo_produto = id_catalogo_produto
        self.nome = nome
        self.lote = lote
        self.data_validade_produto = data_validade_produto # String no formato AAAA-MM-DD
        self.quantidade_vendida = quantidade_vendida
        self.destino = destino
        self.area_origem_id = area_origem_id
        self.usuario_responsavel = usuario_responsavel
        self.data_hora = datetime.now() # Registra o momento da criação da instância

    def to_dict(self) -> Dict[str, Any]:
        """Converte o objeto Venda para um dicionário.

        Returns:
            Dict[str, Any]: Representação da venda em formato de dicionário.
        """
        return {
            'id_catalogo_produto': self.id_catalogo_produto,
            'nome': self.nome,
            'lote': self.lote,
            'data_validade_produto': self.data_validade_produto,
            'quantidade_vendida': self.quantidade_vendida,
            'destino': self.destino,
            'area_origem_id': self.area_origem_id,
            'usuario_responsavel': self.usuario_responsavel,
            'data_hora': self.data_hora.isoformat() # Converte datetime para string no formato ISO
        }

    @staticmethod
    def registrar(venda: 'Venda') -> None:
        """Registra uma nova venda no banco de dados na tabela 'vendas'.

        Args:
            venda (Venda): O objeto Venda a ser registrado.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO vendas (id_catalogo_produto, nome, lote, data_validade_produto,
                               quantidade_vendida, destino, area_origem_id, usuario_responsavel, data_hora)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (venda.id_catalogo_produto, venda.nome, venda.lote, venda.data_validade_produto,
              venda.quantidade_vendida, venda.destino, venda.area_origem_id,
              venda.usuario_responsavel, venda.data_hora.isoformat()))
        conn.commit()
        conn.close()

    @staticmethod
    def listar_todas() -> List['Venda']:
        """Lista todas as vendas registradas no banco de dados da tabela 'vendas',
        ordenadas pela data/hora mais recente.

        Returns:
            List[Venda]: Uma lista de objetos Venda.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM vendas ORDER BY data_hora DESC') # Ordena por data/hora decrescente
        vendas_data = cursor.fetchall()
        conn.close()
        
        vendas_list = []
        for row in vendas_data:
            # Recria o objeto Venda
            v = Venda(row['id_catalogo_produto'], row['nome'], row['lote'], row['data_validade_produto'],
                      row['quantidade_vendida'], row['destino'], row['area_origem_id'],
                      row['usuario_responsavel'])
            # A data_hora lida do BD (string ISO) é usada para definir o atributo datetime.
            if isinstance(row['data_hora'], str):
                 v.data_hora = datetime.fromisoformat(row['data_hora'])
            vendas_list.append(v)
        return vendas_list

def get_produto_catalogo_por_id(id_produto: str) -> Optional[Dict[str, str]]:
    """Busca um produto no catálogo (tabela 'produtos_catalogo') pelo seu ID.

    Args:
        id_produto (str): O ID do produto no catálogo.

    Returns:
        Optional[Dict[str, str]]: Um dicionário com o nome do produto se encontrado, None caso contrário.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT nome FROM produtos_catalogo WHERE id_produto = ?', (id_produto,))
    produto_data = cursor.fetchone()
    conn.close()
    if produto_data:
        return {'nome': produto_data['nome']}
    return None

def popular_dados_iniciais() -> None:
    """Popula o banco de dados com dados iniciais (usuários, produtos do catálogo, áreas e estoque).

    Esta função verifica se o banco já foi populado para evitar duplicidade de dados.
    Os dados inseridos são para fins de demonstração e teste.
    USA 'INSERT OR IGNORE' para evitar erros se os dados já existirem (exceto para produtos_areas).
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Verifica se a tabela de usuários já tem dados para evitar repopulação
    cursor.execute('SELECT COUNT(*) FROM usuarios')
    if cursor.fetchone()['COUNT(*)'] > 0:
        conn.close()
        # print("Banco de dados já populado anteriormente. Verificando consistência de dados iniciais.")
        # Poderia adicionar lógicas para verificar e adicionar apenas o que falta, mas para este exemplo, 
        # se usuários existem, assume-se que o resto também foi populado ou está sendo gerenciado.
        return

    print("Populando banco de dados com dados iniciais...")

    # Inserir usuários (senhas em texto plano para exemplo, NÃO FAÇA ISSO EM PRODUÇÃO)
    cursor.executemany('''
        INSERT OR IGNORE INTO usuarios (username, senha, funcao, nome)
        VALUES (?, ?, ?, ?)
    ''', [
        ('operador1', 'senha123', 'operador', 'João Silva'),
        ('gerente1', 'senhaforte', 'gerente', 'Maria Oliveira')
    ])

    # Inserir produtos no catálogo (tabela 'produtos_catalogo')
    cursor.executemany('''
        INSERT OR IGNORE INTO produtos_catalogo (id_produto, nome)
        VALUES (?, ?)
    ''', [
        ('LEITE001', 'Leite Integral UHT 1L'),
        ('IOG002', 'Iogurte Natural Copo 170g'),
        ('QUE003', 'Queijo Minas Frescal 500g'),
        ('MAN004', 'Manteiga com Sal 200g')
    ])

    # Inserir áreas de armazenamento (tabela 'areas_armazem')
    # CORREÇÃO: Nome da tabela é 'areas_armazem'
    cursor.executemany('''
        INSERT OR IGNORE INTO areas_armazem (id_area, nome, tipo_armazenamento)
        VALUES (?, ?, ?)
    ''', [
        ('A1', 'Refrigerados Rápidos', 'refrigerado'),
        ('B2', 'Congelados Profundos', 'congelado'),
        ('C3', 'Estoque Seco', 'seco')
    ])

    # Inserir produtos nas áreas (estoque inicial na tabela 'produtos_areas')
    # Usar INSERT OR IGNORE pode ser problemático aqui se a intenção é sempre adicionar estes itens
    # como um estado inicial fixo e o schema não tiver constraints UNIQUE apropriadas para todos os campos.
    # Para este exemplo, vamos assumir que se a tabela está vazia, podemos inserir.
    # Se a tabela 'produtos_areas' já tiver dados, esta parte não será executada devido à verificação anterior em 'usuarios'.
    cursor.executemany('''
        INSERT INTO produtos_areas (id_area, id_catalogo_produto, nome, quantidade, data_validade, lote)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', [
        ('A1', 'LEITE001', 'Leite Integral UHT 1L', 100, '2025-12-20', 'LOTE2025A'),
        ('A1', 'IOG002', 'Iogurte Natural Copo 170g', 50, '2025-11-15', 'LOTE2025B'),
        ('A1', 'IOG002', 'Iogurte Natural Copo 170g', 30, '2025-10-10', 'LOTE2025C'), # Mesmo produto, lote diferente
        ('B2', 'QUE003', 'Queijo Minas Frescal 500g', 70, '2025-12-19', 'LOTE2025D'),
        ('C3', 'MAN004', 'Manteiga com Sal 200g', 40, '2026-07-08', 'LOTE2025E')
    ])

    conn.commit()
    conn.close()
    print("Banco de dados populado com sucesso.")

# Chamadas para inicialização e população são feitas em app.py
# if __name__ == '__main__':
#     print(f"Usando banco de dados em: {DATABASE_PATH}")
#     init_db() # Garante que as tabelas existam
#     popular_dados_iniciais() # Popula com dados se estiver vazio
#     print("Verificação de models.py concluída.")

