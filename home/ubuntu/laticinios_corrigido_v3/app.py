# laticinios_armazem/app.py

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime, timedelta, date
import functools
import logging
from models import (
    Usuario, ProdutoLacteo, AreaArmazem, Venda, ProdutoCatalogo,
    popular_dados_iniciais, init_db # Removido get_produto_catalogo_por_id e get_db_connection pois não são usados diretamente aqui
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
    """Decorador para proteger rotas que exigem login e, opcionalmente, uma permissão específica."""
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(*args, **kwargs):
            if 'username' not in session:
                flash("Por favor, faça login para acessar esta página.", "warning")
                return redirect(url_for('login', next=request.url))
            
            # Re-valida a senha da sessão para maior segurança, embora não seja estritamente necessário em todas as requisições
            # Em um sistema de produção, um token de sessão mais robusto seria usado.
            usuario_logado = Usuario.verificar_senha(session['username'], session.get('password'))
            if not usuario_logado:
                session.clear()
                flash("Sua sessão é inválida. Por favor, faça login novamente.", "danger")
                return redirect(url_for('login'))

            if permissao_requerida and not usuario_logado.tem_permissao(permissao_requerida):
                flash("Você não tem permissão para realizar esta ação ou acessar esta página.", "danger")
                # Redireciona para a página anterior ou para a página inicial do armazém
                return redirect(request.referrer or url_for('pagina_inicial_armazem')) 
            
            return view_func(*args, **kwargs)
        return wrapper
    return decorator

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Rota para login de usuários."""
    if request.method == 'POST':
        username = request.form.get('username')
        senha = request.form.get('password')
        usuario = Usuario.verificar_senha(username, senha)

        if usuario:
            session['username'] = usuario.username
            session['user_funcao'] = usuario.funcao
            session['user_nome'] = usuario.nome
            session['password'] = senha # Armazenar a senha na sessão é uma prática insegura para produção.
                                        # Considere usar Flask-Login para gerenciamento de sessão mais seguro.
            app.logger.debug(f"Sessão criada para usuário: {usuario.username}")
            flash(f"Login bem-sucedido! Bem-vindo(a), {usuario.nome}.", "success")
            
            next_url = request.args.get('next')
            return redirect(next_url or url_for('pagina_inicial_armazem'))
        else:
            flash("Usuário ou senha inválidos. Tente novamente.", "danger")
    
    # Se o usuário já estiver logado, redireciona para a página inicial
    if 'username' in session:
        return redirect(url_for('pagina_inicial_armazem'))
        
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Rota para logout de usuários."""
    session.clear()
    flash("Você foi desconectado com sucesso.", "info")
    return redirect(url_for('login'))

# --- Rotas Principais da Aplicação ---
@app.route('/')
@login_necessario()
def index_redirect():
    """Rota raiz da aplicação, redireciona para a página inicial do armazém."""
    return redirect(url_for('pagina_inicial_armazem'))

@app.route('/armazem')
@login_necessario(permissao_requerida='visualizar_armazem')
def pagina_inicial_armazem():
    """Rota para a página inicial do armazém, exibe todas as áreas."""
    areas = AreaArmazem.listar_todas()
    return render_template('armazem.html', areas=areas)

@app.route('/armazem/<id_area>')
@login_necessario(permissao_requerida='detalhes_area')
def detalhes_da_area(id_area):
    """Rota para exibir os detalhes de uma área de armazenamento específica."""
    area = AreaArmazem.buscar_por_id(id_area)
    if not area:
        flash(f"Área com ID '{id_area}' não encontrada.", "danger")
        return redirect(url_for('pagina_inicial_armazem'))
    
    # Lista os produtos na área, ordenados por data de validade
    produtos_na_area = sorted(area.listar_produtos(), key=lambda p: p.data_validade)
    
    # Prepara a lista de produtos do catálogo para o dropdown de adicionar produto
    produtos_catalogo_list = ProdutoCatalogo.listar_todos()
    # Cria um dicionário para facilitar o acesso no template
    produtos_catalogo_dropdown = {pc.id_produto: {'nome': pc.nome} for pc in produtos_catalogo_list}

    return render_template('area_detalhes.html', 
                         area=area, 
                         produtos=produtos_na_area,
                         produtos_catalogo=produtos_catalogo_dropdown,
                         data_hoje=date.today() # Passa a data de hoje para o template (usado para status de validade)
                        )

@app.route('/armazem/<id_area>/adicionar_produto', methods=['POST'])
@login_necessario(permissao_requerida='gerenciar_produtos_em_areas')
def adicionar_produto_na_area(id_area):
    """Rota para adicionar um novo produto a uma área de armazenamento."""
    area = AreaArmazem.buscar_por_id(id_area)
    if not area:
        flash(f"Área '{id_area}' não encontrada.", "danger")
        return redirect(url_for('pagina_inicial_armazem'))

    try:
        id_catalogo_produto = request.form.get('id_produto_catalogo')
        quantidade_str = request.form.get('quantidade')
        data_validade_str = request.form.get('data_validade')
        lote = request.form.get('lote')

        if not all([id_catalogo_produto, quantidade_str, data_validade_str, lote]):
            flash("Todos os campos são obrigatórios para adicionar o produto.", "warning")
            return redirect(url_for('detalhes_da_area', id_area=id_area))

        quantidade = int(quantidade_str)
        if quantidade <= 0:
            flash("A quantidade deve ser um número positivo.", "warning")
            return redirect(url_for('detalhes_da_area', id_area=id_area))

        produto_do_catalogo_obj = ProdutoCatalogo.buscar_por_id(id_catalogo_produto)
        if not produto_do_catalogo_obj:
            flash("Produto do catálogo inválido.", "danger")
            return redirect(url_for('detalhes_da_area', id_area=id_area))

        novo_produto = ProdutoLacteo(
            id_catalogo_produto=id_catalogo_produto,
            nome=produto_do_catalogo_obj.nome, # Nome vem do catálogo
            quantidade=quantidade,
            data_validade_str=data_validade_str,
            lote=lote.strip().upper()
        )
        area.adicionar_produto(novo_produto)
        flash(f"Produto '{novo_produto.nome}' (Lote: {novo_produto.lote}) adicionado/atualizado com sucesso na área {area.nome}!", "success")
    
    except ValueError as e: # Captura erros de conversão (ex: int, data)
        flash(f"Erro ao adicionar produto: {e}", "danger")
    except Exception as e: # Captura outros erros inesperados
        app.logger.error(f"Erro inesperado ao adicionar produto na área {id_area}: {e}", exc_info=True)
        flash("Ocorreu um erro inesperado ao processar sua solicitação.", "danger")
        
    return redirect(url_for('detalhes_da_area', id_area=id_area))

@app.route('/armazem/<id_area>/vender_produto', methods=['POST'])
@login_necessario(permissao_requerida='registrar_venda')
def vender_produto_da_area(id_area):
    """Rota para registrar a venda de um produto de uma área específica."""
    area = AreaArmazem.buscar_por_id(id_area)
    if not area:
        flash(f"Área '{id_area}' não encontrada.", "danger")
        return redirect(url_for('pagina_inicial_armazem'))

    try:
        # O ID do produto na área agora é 'id_instancia_venda' (referente ao 'id' da tabela produtos_areas)
        id_instancia_venda_str = request.form.get('id_instancia_venda') 
        quantidade_venda_str = request.form.get('quantidade_venda')
        destino_venda = request.form.get('destino_venda')

        if not all([id_instancia_venda_str, quantidade_venda_str, destino_venda]):
            flash("Informações insuficientes para registrar a venda.", "warning")
            return redirect(url_for('detalhes_da_area', id_area=id_area))
        
        quantidade_venda = int(quantidade_venda_str)
        id_instancia_venda = int(id_instancia_venda_str)

        if quantidade_venda <= 0:
            flash("A quantidade para venda deve ser positiva.", "warning")
            return redirect(url_for('detalhes_da_area', id_area=id_area))

        # Busca a instância do produto pelo seu ID único na tabela produtos_areas
        produto_para_venda = ProdutoLacteo.buscar_instancia_por_id(id_instancia_venda)

        if not produto_para_venda:
            flash(f"Produto com ID de instância '{id_instancia_venda}' não encontrado.", "danger")
            return redirect(url_for('detalhes_da_area', id_area=id_area))
        
        # Verifica se o produto pertence à área correta (segurança adicional)
        # Esta verificação pode ser mais robusta se o objeto AreaArmazem tiver um método para buscar produto por id_instancia
        produto_na_area_correta = any(p.id == id_instancia_venda for p in area.listar_produtos())
        if not produto_na_area_correta:
            flash(f"Produto com ID de instância '{id_instancia_venda}' não pertence à área '{area.nome}'.", "danger")
            return redirect(url_for('detalhes_da_area', id_area=id_area))

        if produto_para_venda.quantidade < quantidade_venda:
            flash(f"Quantidade insuficiente em estoque para '{produto_para_venda.nome}' (Lote: {produto_para_venda.lote}). Disponível: {produto_para_venda.quantidade}", "warning")
            return redirect(url_for('detalhes_da_area', id_area=id_area))

        # O método remover_produto em AreaArmazem agora usa o id da instância (chave primária)
        sucesso_remocao = area.remover_produto(produto_para_venda.id, quantidade_venda)

        if sucesso_remocao:
            nova_venda = Venda(
                id_catalogo_produto=produto_para_venda.id_catalogo_produto,
                nome=produto_para_venda.nome,
                lote=produto_para_venda.lote,
                data_validade_produto=produto_para_venda.data_validade.strftime('%Y-%m-%d'),
                quantidade_vendida=quantidade_venda,
                destino=destino_venda.strip(),
                area_origem_id=id_area,
                usuario_responsavel=session['username']
            )
            Venda.registrar(nova_venda)
            flash(f"Venda de {quantidade_venda} unidade(s) de '{produto_para_venda.nome}' (Lote: {produto_para_venda.lote}) registrada com sucesso!", "success")
        else:
            flash(f"Falha ao tentar vender {quantidade_venda} unidade(s) de '{produto_para_venda.nome}'. Verifique o estoque ou ID do produto.", "danger")
    
    except ValueError: # Erro na conversão de quantidade ou ID
        flash("Quantidade para venda inválida ou ID do produto inválido. Devem ser números.", "danger")
    except Exception as e:
        app.logger.error(f"Erro inesperado ao vender produto da área {id_area}: {e}", exc_info=True)
        flash("Ocorreu um erro inesperado ao processar a venda.", "danger")

    return redirect(url_for('detalhes_da_area', id_area=id_area))

# --- Rotas de Gerenciamento (CRUD) ---

# CRUD para Áreas de Armazenamento
@app.route('/admin/areas')
@login_necessario(permissao_requerida='gerenciar_areas')
def listar_areas_admin():
    """Rota para listar todas as áreas de armazenamento para administração."""
    areas = AreaArmazem.listar_todas()
    return render_template('admin_listar_areas.html', areas=areas)

@app.route('/admin/areas/adicionar', methods=['GET', 'POST'])
@login_necessario(permissao_requerida='gerenciar_areas')
def adicionar_area():
    """Rota para adicionar uma nova área de armazenamento."""
    if request.method == 'POST':
        id_area = request.form.get('id_area')
        nome = request.form.get('nome')
        tipo_armazenamento = request.form.get('tipo_armazenamento')

        if not all([id_area, nome, tipo_armazenamento]):
            flash("Todos os campos são obrigatórios.", "warning")
        else:
            nova_area = AreaArmazem.criar(id_area.strip().upper(), nome.strip(), tipo_armazenamento)
            if nova_area:
                flash(f"Área '{nova_area.nome}' adicionada com sucesso!", "success")
                return redirect(url_for('listar_areas_admin'))
            else:
                flash(f"Erro ao adicionar área. O ID '{id_area}' já pode existir.", "danger")
    return render_template('admin_form_area.html', acao='Adicionar', area=None)

@app.route('/admin/areas/editar/<id_area_original>', methods=['GET', 'POST'])
@login_necessario(permissao_requerida='gerenciar_areas')
def editar_area(id_area_original):
    """Rota para editar uma área de armazenamento existente."""
    area = AreaArmazem.buscar_por_id(id_area_original)
    if not area:
        flash(f"Área com ID '{id_area_original}' não encontrada.", "danger")
        return redirect(url_for('listar_areas_admin'))

    if request.method == 'POST':
        novo_nome = request.form.get('nome')
        novo_tipo_armazenamento = request.form.get('tipo_armazenamento')

        if not all([novo_nome, novo_tipo_armazenamento]):
            flash("Nome e Tipo de Armazenamento são obrigatórios.", "warning")
        else:
            if area.atualizar(novo_nome.strip(), novo_tipo_armazenamento):
                flash(f"Área '{area.nome}' atualizada com sucesso!", "success")
                return redirect(url_for('listar_areas_admin'))
            else:
                flash("Erro ao atualizar a área.", "danger")
    return render_template('admin_form_area.html', acao='Editar', area=area)

@app.route('/admin/areas/excluir/<id_area>', methods=['POST'])
@login_necessario(permissao_requerida='gerenciar_areas')
def excluir_area(id_area):
    """Rota para excluir uma área de armazenamento."""
    area = AreaArmazem.buscar_por_id(id_area)
    if not area:
        flash(f"Área com ID '{id_area}' não encontrada.", "danger")
    else:
        sucesso, mensagem = area.deletar()
        if sucesso:
            flash(mensagem, "success")
        else:
            flash(mensagem, "danger")
    return redirect(url_for('listar_areas_admin'))

# CRUD para Produtos do Catálogo
@app.route('/admin/catalogo')
@login_necessario(permissao_requerida='gerenciar_catalogo_produtos')
def listar_produtos_catalogo_admin():
    """Rota para listar todos os produtos do catálogo para administração."""
    produtos = ProdutoCatalogo.listar_todos()
    return render_template('admin_listar_produtos_catalogo.html', produtos=produtos)

@app.route('/admin/catalogo/adicionar', methods=['GET', 'POST'])
@login_necessario(permissao_requerida='gerenciar_catalogo_produtos')
def adicionar_produto_catalogo():
    """Rota para adicionar um novo produto ao catálogo."""
    if request.method == 'POST':
        id_produto = request.form.get('id_produto')
        nome = request.form.get('nome')

        if not all([id_produto, nome]):
            flash("ID do Produto e Nome são obrigatórios.", "warning")
        else:
            novo_produto = ProdutoCatalogo.criar(id_produto.strip().upper(), nome.strip())
            if novo_produto:
                flash(f"Produto '{novo_produto.nome}' adicionado ao catálogo com sucesso!", "success")
                return redirect(url_for('listar_produtos_catalogo_admin'))
            else:
                flash(f"Erro ao adicionar produto ao catálogo. O ID '{id_produto}' já pode existir.", "danger")
    return render_template('admin_form_produto_catalogo.html', acao='Adicionar', produto=None)

@app.route('/admin/catalogo/editar/<id_produto_catalogo>', methods=['GET', 'POST'])
@login_necessario(permissao_requerida='gerenciar_catalogo_produtos')
def editar_produto_catalogo(id_produto_catalogo):
    """Rota para editar um produto existente no catálogo."""
    produto = ProdutoCatalogo.buscar_por_id(id_produto_catalogo)
    if not produto:
        flash(f"Produto do catálogo com ID '{id_produto_catalogo}' não encontrado.", "danger")
        return redirect(url_for('listar_produtos_catalogo_admin'))

    if request.method == 'POST':
        novo_nome = request.form.get('nome')
        if not novo_nome:
            flash("O nome do produto é obrigatório.", "warning")
        else:
            if produto.atualizar(novo_nome.strip()):
                flash(f"Produto '{produto.nome}' atualizado com sucesso!", "success")
                return redirect(url_for('listar_produtos_catalogo_admin'))
            else:
                flash("Erro ao atualizar o produto no catálogo.", "danger")
    return render_template('admin_form_produto_catalogo.html', acao='Editar', produto=produto)

@app.route('/admin/catalogo/excluir/<id_produto_catalogo>', methods=['POST'])
@login_necessario(permissao_requerida='gerenciar_catalogo_produtos')
def excluir_produto_catalogo(id_produto_catalogo):
    """Rota para excluir um produto do catálogo."""
    produto = ProdutoCatalogo.buscar_por_id(id_produto_catalogo)
    if not produto:
        flash(f"Produto do catálogo com ID '{id_produto_catalogo}' não encontrado.", "danger")
    else:
        sucesso, mensagem = produto.deletar()
        if sucesso:
            flash(mensagem, "success")
        else:
            flash(mensagem, "danger")
    return redirect(url_for('listar_produtos_catalogo_admin'))

# CRUD para Instâncias de Produtos em Áreas (produtos_areas)
# A chave primária da instância do produto é 'id_instancia_produto' na URL e na lógica interna
@app.route('/admin/area/<id_area>/produto/<int:id_instancia_produto>/editar', methods=['GET', 'POST'])
@login_necessario(permissao_requerida='gerenciar_produtos_em_areas')
def editar_produto_em_area(id_area, id_instancia_produto):
    """Rota para editar uma instância de produto específica em uma área."""
    area = AreaArmazem.buscar_por_id(id_area)
    if not area:
        flash(f"Área com ID '{id_area}' não encontrada.", "danger")
        return redirect(url_for('pagina_inicial_armazem'))

    # Busca a instância do produto pelo seu ID (chave primária da tabela produtos_areas)
    produto_instancia = ProdutoLacteo.buscar_instancia_por_id(id_instancia_produto)
    if not produto_instancia:
        flash(f"Instância de produto com ID '{id_instancia_produto}' não encontrada.", "danger")
        return redirect(url_for('detalhes_da_area', id_area=id_area))
    
    # Validação adicional: verifica se o produto realmente pertence à área especificada na URL
    # Isso é uma camada extra de segurança, embora buscar_instancia_por_id já seja específico.
    produto_encontrado_na_area = any(p.id == id_instancia_produto for p in area.listar_produtos())
    if not produto_encontrado_na_area:
        flash(f"Produto com ID de instância '{id_instancia_produto}' não pertence à área '{area.nome}'.", "danger")
        return redirect(url_for('detalhes_da_area', id_area=id_area))

    if request.method == 'POST':
        nova_quantidade_str = request.form.get('quantidade')
        nova_data_validade_str = request.form.get('data_validade')
        novo_lote = request.form.get('lote')

        if not all([nova_quantidade_str, nova_data_validade_str, novo_lote]):
            flash("Todos os campos (Quantidade, Data de Validade, Lote) são obrigatórios.", "warning")
        else:
            try:
                nova_quantidade = int(nova_quantidade_str)
                if nova_quantidade < 0: # Permitir 0 para caso de remoção total via edição, mas não negativo
                    flash("A quantidade não pode ser negativa.", "warning")
                # O método atualizar_instancia já lida com a conversão da data
                elif produto_instancia.atualizar_instancia(nova_quantidade, nova_data_validade_str, novo_lote.strip().upper()):
                    flash(f"Produto '{produto_instancia.nome}' (Lote: {produto_instancia.lote}) atualizado com sucesso na área {area.nome}!", "success")
                    return redirect(url_for('detalhes_da_area', id_area=id_area))
                else:
                    flash("Erro ao atualizar o produto. Verifique os dados (ex: formato da data AAAA-MM-DD).", "danger")
            except ValueError: # Erro na conversão da quantidade
                flash("Quantidade inválida. Deve ser um número.", "danger")
            except Exception as e:
                app.logger.error(f"Erro ao editar produto {id_instancia_produto} na área {id_area}: {e}", exc_info=True)
                flash("Ocorreu um erro inesperado ao atualizar o produto.", "danger")
                
    return render_template('admin_form_produto_area.html', 
                           acao='Editar', 
                           area=area, 
                           produto=produto_instancia)

@app.route('/admin/area/<id_area>/produto/<int:id_instancia_produto>/excluir', methods=['POST'])
@login_necessario(permissao_requerida='gerenciar_produtos_em_areas')
def excluir_produto_de_area(id_area, id_instancia_produto):
    """Rota para excluir completamente uma instância de produto de uma área."""
    area = AreaArmazem.buscar_por_id(id_area)
    if not area:
        flash(f"Área com ID '{id_area}' não encontrada.", "danger")
        return redirect(url_for('pagina_inicial_armazem'))

    produto_instancia = ProdutoLacteo.buscar_instancia_por_id(id_instancia_produto)
    if not produto_instancia:
        flash(f"Instância de produto com ID '{id_instancia_produto}' não encontrada.", "danger")
    else:
        # Validação extra para garantir que o produto pertence à área (opcional, mas bom)
        produto_na_area_correta = any(p.id == id_instancia_produto for p in area.listar_produtos())
        if not produto_na_area_correta:
            flash(f"Produto com ID de instância '{id_instancia_produto}' não pertence à área '{area.nome}'.", "danger")
        elif produto_instancia.deletar_instancia():
            flash(f"Produto '{produto_instancia.nome}' (Lote: {produto_instancia.lote}) excluído com sucesso da área {area.nome}!", "success")
        else:
            flash(f"Erro ao excluir o produto '{produto_instancia.nome}' da área.", "danger")
            
    return redirect(url_for('detalhes_da_area', id_area=id_area))

# FIM CRUD para Instâncias de Produtos em Áreas

@app.route('/relatorios')
@login_necessario(permissao_requerida='gerente')
def pagina_relatorios():
    """Rota para a página de relatórios."""
    # Calcula o estoque total por produto (do catálogo)
    estoque_total = {}
    for area_obj in AreaArmazem.listar_todas():
        for prod_instancia in area_obj.listar_produtos():
            chave_produto = prod_instancia.id_catalogo_produto 
            if chave_produto not in estoque_total:
                estoque_total[chave_produto] = {"nome": prod_instancia.nome, "quantidade_total": 0}
            estoque_total[chave_produto]["quantidade_total"] += prod_instancia.quantidade
    
    # Lista todas as vendas registradas, ordenadas pela mais recente
    vendas = sorted([v.to_dict() for v in Venda.listar_todas()], key=lambda x: datetime.strptime(x['data_hora'], '%d/%m/%Y %H:%M:%S'), reverse=True)

    # Identifica produtos próximos do vencimento ou vencidos
    dias_alerta_antecedencia = 7 
    data_hoje_obj = date.today()
    limite_alerta = data_hoje_obj + timedelta(days=dias_alerta_antecedencia)
    produtos_alerta_validade = []

    for area_obj in AreaArmazem.listar_todas():
        for produto_obj in area_obj.listar_produtos(): # produto_obj é uma instância de ProdutoLacteo
            status_validade = ""
            # A data de validade já é um objeto date em ProdutoLacteo
            dias_para_vencer_calc = (produto_obj.data_validade - data_hoje_obj).days

            if produto_obj.data_validade < data_hoje_obj:
                status_validade = "VENCIDO"
            elif produto_obj.data_validade <= limite_alerta:
                status_validade = "PROXIMO_VENCIMENTO"
            
            if status_validade:
                produtos_alerta_validade.append({
                    "area_id": area_obj.id_area,
                    "nome_area": area_obj.nome,
                    "produto": produto_obj.to_dict(), # Converte a instância para dicionário
                    "status_validade": status_validade,
                    "dias_para_vencer": dias_para_vencer_calc
                })
    
    # Ordena os alertas: VENCIDO primeiro, depois por dias para vencer
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
    """Endpoint da API para listar produtos de uma área específica em formato JSON."""
    area = AreaArmazem.buscar_por_id(id_area)
    if not area:
        return jsonify({"erro": "Área não encontrada"}), 404
    return jsonify(area.to_dict()) # to_dict() em AreaArmazem já inclui os produtos

@app.route('/api/estoque_geral', methods=['GET'])
@login_necessario(permissao_requerida='gerente')
def api_estoque_geral():
    """Endpoint da API para listar o estoque completo de todas as áreas em formato JSON."""
    estoque_completo = [area.to_dict() for area in AreaArmazem.listar_todas()]
    return jsonify(estoque_completo)

# --- Context Processor ---
@app.context_processor
def injetar_dados_globais():
    """Disponibiliza variáveis globais para todos os templates."""
    user_info = None
    if 'username' in session:
        user_info = {
            'username': session.get('username'),
            'funcao': session.get('user_funcao'),
            'nome': session.get('user_nome')
            # Não é seguro injetar a senha aqui, mesmo que esteja na sessão.
        }
    return dict(usuario_logado=user_info, data_hoje_global=date.today())

# Ponto de entrada para executar a aplicação Flask
if __name__ == '__main__':
    # Executa a aplicação em modo de depuração, acessível na rede local.
    # Em produção, use um servidor WSGI como Gunicorn ou uWSGI.
    app.run(debug=True, host='0.0.0.0', port=5001) # Porta padrão 5001

