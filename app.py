# laticinios_armazem/app.py

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime, timedelta, date
import functools
import logging
from models import (
    Usuario, ProdutoLacteo, AreaArmazem, Venda,
    get_produto_catalogo_por_id, popular_dados_iniciais, init_db, get_db_connection
)

# Inicializa a aplicação Flask
app = Flask(__name__)
# Define uma chave secreta para a sessão. Em produção, use uma chave mais segura e gerada aleatoriamente.
app.secret_key = 'chave_secreta_para_sessoes_flask_laticinios_minerva'

# Configura o logging básico para a aplicação, útil para depuração.
logging.basicConfig(level=logging.DEBUG)

# Filtro Jinja2 personalizado para converter strings de data em objetos date.
def to_date_filter(value):
    """Converte uma string de data (AAAA-MM-DD) para um objeto date.
    Se o valor já for um objeto date, retorna o próprio valor.
    Retorna o valor original em caso de erro na conversão.
    """
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (ValueError, TypeError) as e:
        logging.error(f"Erro ao converter data: {value}, erro: {e}")
        return value

# Registra o filtro personalizado no ambiente Jinja2 da aplicação.
app.jinja_env.filters['to_date'] = to_date_filter

# Inicializa o banco de dados (cria tabelas se não existirem).
init_db()

# Popula o banco de dados com dados iniciais (se ainda não estiver populado).
popular_dados_iniciais()

# --- Autenticação e Controle de Acesso ---
def login_necessario(permissao_requerida: str = None):
    """Decorador para proteger rotas que exigem login e, opcionalmente, uma permissão específica.

    Args:
        permissao_requerida (str, optional): A permissão necessária para acessar a rota.
                                            Se None, apenas o login é verificado.
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(*args, **kwargs):
            # Verifica se o usuário está logado (se 'username' está na sessão)
            if 'username' not in session:
                flash("Por favor, faça login para acessar esta página.", "warning")
                return redirect(url_for('login', next=request.url)) # Redireciona para login, guardando a URL original
            
            # Verifica se a senha na sessão ainda é válida para o usuário logado
            # ATENÇÃO: Armazenar a senha na sessão (mesmo que para revalidação) não é uma boa prática de segurança.
            # Considere usar tokens de sessão mais robustos ou revalidação de identidade de outras formas.
            usuario_logado = Usuario.verificar_senha(session['username'], session.get('password'))
            if not usuario_logado:
                session.clear() # Limpa a sessão inválida
                flash("Sua sessão é inválida. Por favor, faça login novamente.", "danger")
                return redirect(url_for('login'))

            # Verifica se o usuário tem a permissão requerida (se uma foi especificada)
            if permissao_requerida and not usuario_logado.tem_permissao(permissao_requerida):
                flash("Você não tem permissão para realizar esta ação ou acessar esta página.", "danger")
                # Redireciona para a página anterior ou para a página inicial do armazém
                return redirect(request.referrer or url_for('pagina_inicial_armazem')) 
            
            return view_func(*args, **kwargs) # Permite o acesso à rota
        return wrapper
    return decorator

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Rota para login de usuários.

    Se o método for POST, tenta autenticar o usuário com os dados do formulário.
    Se o login for bem-sucedido, armazena informações do usuário na sessão e redireciona.
    Se o usuário já estiver logado, redireciona para a página inicial do armazém.
    """
    if request.method == 'POST':
        username = request.form.get('username')
        senha = request.form.get('password')
        usuario = Usuario.verificar_senha(username, senha)

        if usuario:
            # Armazena informações do usuário na sessão
            session['username'] = usuario.username
            session['user_funcao'] = usuario.funcao
            session['user_nome'] = usuario.nome
            # ATENÇÃO: Armazenar a senha na sessão é uma falha de segurança.
            session['password'] = senha  # Usado pelo decorador login_necessario para revalidar
            app.logger.debug(f"Sessão criada para usuário: {usuario.username}")
            flash(f"Login bem-sucedido! Bem-vindo(a), {usuario.nome}.", "success")
            
            next_url = request.args.get('next') # Obtém a URL de redirecionamento (se houver)
            return redirect(next_url or url_for('pagina_inicial_armazem'))
        else:
            flash("Usuário ou senha inválidos. Tente novamente.", "danger")
    
    # Se o usuário já estiver logado, redireciona para a página inicial
    if 'username' in session:
        return redirect(url_for('pagina_inicial_armazem'))
        
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Rota para logout de usuários.

    Limpa a sessão e redireciona para a página de login.
    """
    session.clear()
    flash("Você foi desconectado com sucesso.", "info")
    return redirect(url_for('login'))

# --- Rotas Principais da Aplicação ---
@app.route('/')
@login_necessario() # Protege a rota, exigindo login
def index_redirect():
    """Rota raiz da aplicação.

    Redireciona para a página inicial do armazém se o usuário estiver logado.
    """
    return redirect(url_for('pagina_inicial_armazem'))

@app.route('/armazem')
@login_necessario(permissao_requerida='visualizar_armazem') # Exige login e permissão
def pagina_inicial_armazem():
    """Rota para a página inicial do armazém.

    Lista todas as áreas de armazenamento cadastradas.
    """
    # CORREÇÃO: Nome da tabela corrigido de 'areas_armazenamento' para 'areas_armazem'
    areas = AreaArmazem.listar_todas() 
    return render_template('armazem.html', areas=areas)

@app.route('/armazem/<id_area>')
@login_necessario(permissao_requerida='detalhes_area') # Exige login e permissão
def detalhes_da_area(id_area):
    """Rota para exibir os detalhes de uma área de armazenamento específica.

    Mostra informações da área e os produtos nela contidos.
    Args:
        id_area (str): O ID da área a ser visualizada.
    """
    area = AreaArmazem.buscar_por_id(id_area)
    if not area:
        flash(f"Área com ID '{id_area}' não encontrada.", "danger")
        return redirect(url_for('pagina_inicial_armazem'))
    
    # Lista os produtos da área, ordenados por data de validade
    produtos_na_area = sorted(area.listar_produtos(), key=lambda p: p.data_validade)
    app.logger.debug(f"Produtos na área {id_area}: {[p.to_dict() for p in produtos_na_area]}")
    
    # Obtém a lista de produtos do catálogo para o formulário de adição
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id_produto, nome FROM produtos_catalogo')
    # Cria um dicionário com os produtos do catálogo para fácil acesso no template
    produtos_catalogo = {row['id_produto']: {'nome': row['nome']} for row in cursor.fetchall()}
    conn.close()
    
    return render_template('area_detalhes.html', 
                         area=area, 
                         produtos=produtos_na_area,
                         produtos_catalogo=produtos_catalogo,
                         data_hoje=date.today() # Passa a data atual para o template
                        )

@app.route('/armazem/<id_area>/adicionar_produto', methods=['POST'])
@login_necessario(permissao_requerida='gerente') # Exige login e permissão de gerente
def adicionar_produto_na_area(id_area):
    """Rota para adicionar um novo produto a uma área de armazenamento.

    Processa os dados do formulário de adição de produto.
    Args:
        id_area (str): O ID da área onde o produto será adicionado.
    """
    area = AreaArmazem.buscar_por_id(id_area)
    if not area:
        flash(f"Área '{id_area}' não encontrada.", "danger")
        return redirect(url_for('pagina_inicial_armazem'))

    try:
        # Obtém os dados do formulário
        id_catalogo_produto = request.form.get('id_produto_catalogo')
        quantidade_str = request.form.get('quantidade')
        data_validade_str = request.form.get('data_validade')
        lote = request.form.get('lote')

        # Validação básica dos campos
        if not all([id_catalogo_produto, quantidade_str, data_validade_str, lote]):
            flash("Todos os campos são obrigatórios para adicionar o produto.", "warning")
            return redirect(url_for('detalhes_da_area', id_area=id_area))

        quantidade = int(quantidade_str)
        if quantidade <= 0:
            flash("A quantidade deve ser um número positivo.", "warning")
            return redirect(url_for('detalhes_da_area', id_area=id_area))

        produto_do_catalogo = get_produto_catalogo_por_id(id_catalogo_produto)
        if not produto_do_catalogo:
            flash("Produto do catálogo inválido.", "danger")
            return redirect(url_for('detalhes_da_area', id_area=id_area))

        # Cria uma instância do novo produto
        novo_produto = ProdutoLacteo(
            id_catalogo_produto=id_catalogo_produto,
            nome=produto_do_catalogo['nome'],
            quantidade=quantidade,
            data_validade_str=data_validade_str,
            lote=lote.strip().upper() # Remove espaços e converte para maiúsculas
        )
        area.adicionar_produto(novo_produto) # Adiciona o produto à área (lógica no models.py)
        flash(f"Produto '{novo_produto.nome}' (Lote: {novo_produto.lote}) adicionado/atualizado com sucesso na área {area.nome}!", "success")
    
    except ValueError as e: # Erro na conversão de quantidade ou data
        flash(f"Erro ao adicionar produto: {e}", "danger")
    except Exception as e: # Outros erros inesperados
        app.logger.error(f"Erro inesperado ao adicionar produto na área {id_area}: {e}", exc_info=True)
        flash("Ocorreu um erro inesperado ao processar sua solicitação.", "danger")
        
    return redirect(url_for('detalhes_da_area', id_area=id_area))

@app.route('/armazem/<id_area>/vender_produto', methods=['POST'])
@login_necessario(permissao_requerida='registrar_venda') # Exige login e permissão para registrar venda
def vender_produto_da_area(id_area):
    """Rota para registrar a venda de um produto de uma área específica.

    Processa os dados do formulário de venda.
    Args:
        id_area (str): O ID da área de onde o produto será vendido.
    """
    area = AreaArmazem.buscar_por_id(id_area)
    if not area:
        flash(f"Área '{id_area}' não encontrada.", "danger")
        return redirect(url_for('pagina_inicial_armazem'))

    try:
        # Obtém os dados do formulário de venda
        id_produto_catalogo = request.form.get('id_produto_catalogo_venda')
        lote = request.form.get('lote_venda')
        quantidade_venda_str = request.form.get('quantidade_venda')
        destino_venda = request.form.get('destino_venda')

        # Validação básica dos campos
        if not all([id_produto_catalogo, lote, quantidade_venda_str, destino_venda]):
            flash("Informações insuficientes para registrar a venda.", "warning")
            return redirect(url_for('detalhes_da_area', id_area=id_area))
        
        quantidade_venda = int(quantidade_venda_str)
        if quantidade_venda <= 0:
            flash("A quantidade para venda deve ser positiva.", "warning")
            return redirect(url_for('detalhes_da_area', id_area=id_area))

        # Busca o produto específico na área para venda
        produto_para_venda = None
        for produto_em_estoque in area.listar_produtos():
            if produto_em_estoque.id_catalogo_produto == id_produto_catalogo and produto_em_estoque.lote == lote:
                produto_para_venda = produto_em_estoque
                break

        if not produto_para_venda:
            flash(f"Produto com ID '{id_produto_catalogo}' e lote '{lote}' não encontrado nesta área.", "danger")
            return redirect(url_for('detalhes_da_area', id_area=id_area))

        if produto_para_venda.quantidade < quantidade_venda:
            flash(f"Quantidade insuficiente em estoque para '{produto_para_venda.nome}' (Lote: {produto_para_venda.lote}). Disponível: {produto_para_venda.quantidade}", "warning")
            return redirect(url_for('detalhes_da_area', id_area=id_area))

        # Remove a quantidade vendida do estoque da área
        sucesso_remocao = area.remover_produto(id_produto_catalogo, lote, quantidade_venda)

        if sucesso_remocao:
            # Cria e registra a venda
            nova_venda = Venda(
                id_catalogo_produto=id_produto_catalogo,
                nome=produto_para_venda.nome,
                lote=lote,
                data_validade_produto=produto_para_venda.data_validade.strftime('%Y-%m-%d'),
                quantidade_vendida=quantidade_venda,
                destino=destino_venda,
                area_origem_id=id_area,
                usuario_responsavel=session['username']
            )
            Venda.registrar(nova_venda)
            flash(f"Venda de {quantidade_venda} unidade(s) de '{produto_para_venda.nome}' (Lote: {produto_para_venda.lote}) registrada com sucesso!", "success")
        else:
            # Este caso teoricamente não deveria ocorrer devido às verificações anteriores, mas é uma salvaguarda.
            flash(f"Falha ao tentar vender {quantidade_venda} unidade(s) de '{produto_para_venda.nome}'. Verifique o estoque.", "danger")
    
    except ValueError: # Erro na conversão da quantidade_venda
        flash("Quantidade para venda inválida. Deve ser um número.", "danger")
    except Exception as e: # Outros erros inesperados
        app.logger.error(f"Erro inesperado ao vender produto da área {id_area}: {e}", exc_info=True)
        flash("Ocorreu um erro inesperado ao processar a venda.", "danger")

    return redirect(url_for('detalhes_da_area', id_area=id_area))

@app.route('/relatorios')
@login_necessario(permissao_requerida='gerente') # Exige login e permissão de gerente
def pagina_relatorios():
    """Rota para a página de relatórios.

    Exibe informações como estoque total, vendas registradas e produtos com alerta de validade.
    """
    # Calcula o estoque total de cada produto (somando de todas as áreas)
    estoque_total = {}
    for area_obj in AreaArmazem.listar_todas():
        for prod_instancia in area_obj.listar_produtos():
            chave_produto = prod_instancia.id_catalogo_produto 
            if chave_produto not in estoque_total:
                estoque_total[chave_produto] = {"nome": prod_instancia.nome, "quantidade_total": 0}
            estoque_total[chave_produto]["quantidade_total"] += prod_instancia.quantidade
    
    # Lista todas as vendas, ordenadas da mais recente para a mais antiga
    vendas = sorted([v.to_dict() for v in Venda.listar_todas()], key=lambda x: x['data_hora'], reverse=True)

    # Define o período de alerta para produtos próximos do vencimento
    dias_alerta_antecedencia = 7 
    data_hoje_obj = date.today()
    limite_alerta = data_hoje_obj + timedelta(days=dias_alerta_antecedencia)
    produtos_alerta_validade = []

    # Identifica produtos vencidos ou próximos do vencimento
    for area_obj in AreaArmazem.listar_todas():
        for produto_obj in area_obj.listar_produtos():
            status_validade = ""
            dias_para_vencer_calc = (produto_obj.data_validade - data_hoje_obj).days

            if produto_obj.data_validade < data_hoje_obj:
                status_validade = "VENCIDO"
            elif produto_obj.data_validade <= limite_alerta:
                status_validade = "PROXIMO_VENCIMENTO"
            
            if status_validade: # Adiciona à lista de alerta se houver um status
                produtos_alerta_validade.append({
                    "area_id": area_obj.id_area,
                    "nome_area": area_obj.nome,
                    "produto": produto_obj.to_dict(),
                    "status_validade": status_validade,
                    "dias_para_vencer": dias_para_vencer_calc
                })
    
    # Ordena os produtos em alerta (Vencidos primeiro, depois por dias para vencer)
    produtos_alerta_validade.sort(key=lambda x: (x["status_validade"] != "VENCIDO", x["dias_para_vencer"]))

    return render_template('relatorios.html', 
                         estoque_total=estoque_total, 
                         vendas_registradas=vendas, 
                         produtos_alerta_validade=produtos_alerta_validade,
                         dias_alerta=dias_alerta_antecedencia)

# --- API Endpoints (Exemplos) ---
@app.route('/api/armazem/<id_area>/produtos', methods=['GET'])
@login_necessario(permissao_requerida='visualizar_armazem')
def api_produtos_por_area(id_area):
    """Endpoint da API para listar produtos de uma área específica em formato JSON.

    Args:
        id_area (str): O ID da área.
    Returns:
        Response: JSON com os dados da área e seus produtos, ou erro 404 se a área não for encontrada.
    """
    area = AreaArmazem.buscar_por_id(id_area)
    if not area:
        return jsonify({"erro": "Área não encontrada"}), 404
    return jsonify(area.to_dict()) # Retorna os dados da área (incluindo produtos) como JSON

@app.route('/api/estoque_geral', methods=['GET'])
@login_necessario(permissao_requerida='gerente')
def api_estoque_geral():
    """Endpoint da API para listar o estoque completo de todas as áreas em formato JSON.

    Returns:
        Response: JSON com uma lista de todas as áreas e seus respectivos produtos.
    """
    estoque_completo = [area.to_dict() for area in AreaArmazem.listar_todas()]
    return jsonify(estoque_completo)

# --- Context Processor ---
@app.context_processor
def injetar_dados_globais():
    """Disponibiliza variáveis globais para todos os templates.

    Isso é útil para dados que são frequentemente necessários nos templates,
    como informações do usuário logado ou a data atual.
    """
    user_info = None
    if 'username' in session:
        user_info = {
            'username': session.get('username'),
            'funcao': session.get('user_funcao'),
            'nome': session.get('user_nome')
        }
    return dict(usuario_logado=user_info, data_hoje_global=date.today())

# Ponto de entrada para executar a aplicação Flask
if __name__ == '__main__':
    # Executa a aplicação em modo de depuração, acessível na rede local.
    app.run(debug=True, host='0.0.0.0', port=5002)
