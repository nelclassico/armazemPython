# laticinios_armazem/app.py

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime, timedelta, date
import functools
import logging

# Importar modelos e funções do models.py
from models import (
    Usuario, ProdutoLacteo, AreaArmazem, Venda,
    db_usuarios, db_areas_armazem, db_vendas_registradas, db_produtos_catalogo,
    get_produto_catalogo_por_id, popular_dados_iniciais
)

app = Flask(__name__)
app.secret_key = 'chave_secreta_para_sessoes_flask_laticinios_minerva'

# Configurar logging básico
logging.basicConfig(level=logging.DEBUG)

# Filtro personalizado para converter string de data em objeto date
def to_date_filter(value):
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (ValueError, TypeError) as e:
        logging.error(f"Erro ao converter data: {value}, erro: {e}")
        return value

# Registrar o filtro no ambiente Jinja2
app.jinja_env.filters['to_date'] = to_date_filter

# Assegura que os dados iniciais sejam carregados
if not any(db_areas_armazem[id_area]["produtos"] for id_area in db_areas_armazem):
    app.logger.info("Populando dados iniciais pois o armazém está vazio.")
    popular_dados_iniciais()

# --- Autenticação e Controle de Acesso ---
def login_necessario(permissao_requerida: str = None):
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(*args, **kwargs):
            if 'username' not in session:
                flash("Por favor, faça login para acessar esta página.", "warning")
                return redirect(url_for('login', next=request.url))
            
            user_data = db_usuarios.get(session['username'])
            if not user_data:
                session.clear()
                flash("Sua sessão é inválida. Por favor, faça login novamente.", "danger")
                return redirect(url_for('login'))

            usuario_logado = Usuario(
                username=session['username'],
                funcao=session['user_funcao'],
                nome=session['user_nome']
            )

            if permissao_requerida and not usuario_logado.tem_permissao(permissao_requerida):
                flash("Você não tem permissão para realizar esta ação ou acessar esta página.", "danger")
                return redirect(request.referrer or url_for('pagina_inicial_armazem')) 
            
            return view_func(*args, **kwargs)
        return wrapper
    return decorator

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        senha = request.form.get('password')
        usuario = Usuario.verificar_senha(username, senha)

        if usuario:
            session['username'] = usuario.username
            session['user_funcao'] = usuario.funcao
            session['user_nome'] = usuario.nome
            app.logger.debug(f"Sessão criada para usuário: {usuario.username}")
            flash(f"Login bem-sucedido! Bem-vindo(a), {usuario.nome}.", "success")
            
            next_url = request.args.get('next')
            return redirect(next_url or url_for('pagina_inicial_armazem'))
        else:
            flash("Usuário ou senha inválidos. Tente novamente.", "danger")
    
    if 'username' in session:
        return redirect(url_for('pagina_inicial_armazem'))
        
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Você foi desconectado com sucesso.", "info")
    return redirect(url_for('login'))

# --- Rotas Principais da Aplicação ---
@app.route('/')
@login_necessario()
def index_redirect():
    return redirect(url_for('pagina_inicial_armazem'))

@app.route('/armazem')
@login_necessario(permissao_requerida='visualizar_armazem')
def pagina_inicial_armazem():
    areas = AreaArmazem.listar_todas()
    return render_template('armazem.html', areas=areas)

@app.route('/armazem/<id_area>')
@login_necessario(permissao_requerida='detalhes_area')
def detalhes_da_area(id_area):
    area = AreaArmazem.buscar_por_id(id_area)
    if not area:
        flash(f"Área com ID '{id_area}' não encontrada.", "danger")
        return redirect(url_for('pagina_inicial_armazem'))
    
    produtos_na_area = sorted(area.listar_produtos(), key=lambda p: p.data_validade)
    app.logger.debug(f"Produtos na área {id_area}: {[p.to_dict() for p in produtos_na_area]}")
    app.logger.debug(f"Tipo de produtos_catalogo: {type(db_produtos_catalogo)}, Conteúdo: {db_produtos_catalogo}")
    
    return render_template('area_detalhes.html', 
                         area=area, 
                         produtos=produtos_na_area,
                         produtos_catalogo=db_produtos_catalogo,
                         data_hoje=date.today())

@app.route('/armazem/<id_area>/adicionar_produto', methods=['POST'])
@login_necessario(permissao_requerida='gerente')
def adicionar_produto_na_area(id_area):
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

        produto_do_catalogo = get_produto_catalogo_por_id(id_catalogo_produto)
        if not produto_do_catalogo:
            flash("Produto do catálogo inválido.", "danger")
            return redirect(url_for('detalhes_da_area', id_area=id_area))

        novo_produto = ProdutoLacteo(
            id_catalogo_produto=id_catalogo_produto,
            nome=produto_do_catalogo['nome'],
            quantidade=quantidade,
            data_validade_str=data_validade_str,
            lote=lote.strip().upper()
        )
        area.adicionar_produto(novo_produto)
        flash(f"Produto '{novo_produto.nome}' (Lote: {novo_produto.lote}) adicionado/atualizado com sucesso na área {area.nome}!", "success")
    
    except ValueError as e:
        flash(f"Erro ao adicionar produto: {e}", "danger")
    except Exception as e:
        app.logger.error(f"Erro inesperado ao adicionar produto na área {id_area}: {e}", exc_info=True)
        flash("Ocorreu um erro inesperado ao processar sua solicitação.", "danger")
        
    return redirect(url_for('detalhes_da_area', id_area=id_area))

@app.route('/armazem/<id_area>/vender_produto', methods=['POST'])
@login_necessario(permissao_requerida='registrar_venda')
def vender_produto_da_area(id_area):
    area = AreaArmazem.buscar_por_id(id_area)
    if not area:
        flash(f"Área '{id_area}' não encontrada.", "danger")
        return redirect(url_for('pagina_inicial_armazem'))

    try:
        id_produto_catalogo = request.form.get('id_produto_catalogo_venda')
        lote = request.form.get('lote_venda')
        quantidade_venda_str = request.form.get('quantidade_venda')
        destino_venda = request.form.get('destino_venda')

        if not all([id_produto_catalogo, lote, quantidade_venda_str, destino_venda]):
            flash("Informações insuficientes para registrar a venda.", "warning")
            return redirect(url_for('detalhes_da_area', id_area=id_area))
        
        quantidade_venda = int(quantidade_venda_str)
        if quantidade_venda <= 0:
            flash("A quantidade para venda deve ser positiva.", "warning")
            return redirect(url_for('detalhes_da_area', id_area=id_area))

        produto_para_venda = None
        for produto in area.listar_produtos():
            if produto.id_produto_catalogo == id_produto_catalogo and produto.lote == lote:
                produto_para_venda = produto
                break

        if not produto_para_venda:
            flash(f"Produto com ID '{id_produto_catalogo}' e lote '{lote}' não encontrado nesta área.", "danger")
            return redirect(url_for('detalhes_da_area', id_area=id_area))

        if produto_para_venda.quantidade < quantidade_venda:
            flash(f"Quantidade insuficiente em estoque para '{produto_para_venda.nome}' (Lote: {produto_para_venda.lote}). Disponível: {produto_para_venda.quantidade}", "warning")
            return redirect(url_for('detalhes_da_area', id_area=id_area))

        sucesso_remocao = area.remover_produto(id_produto_catalogo, lote, quantidade_venda)

        if sucesso_remocao:
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
            flash(f"Falha ao tentar vender {quantidade_venda} unidade(s) de '{produto_para_venda.nome}'. Verifique o estoque.", "danger")
    
    except ValueError:
        flash("Quantidade para venda inválida. Deve ser um número.", "danger")
    except Exception as e:
        app.logger.error(f"Erro inesperado ao vender produto da área {id_area}: {e}", exc_info=True)
        flash("Ocorreu um erro inesperado ao processar a venda.", "danger")

    return redirect(url_for('detalhes_da_area', id_area=id_area))

@app.route('/relatorios')
@login_necessario(permissao_requerida='gerente')
def pagina_relatorios():
    estoque_total = {}
    for area_obj in AreaArmazem.listar_todas():
        for prod_instancia in area_obj.listar_produtos():
            chave_produto = prod_instancia.id_catalogo_produto 
            if chave_produto not in estoque_total:
                estoque_total[chave_produto] = {"nome": prod_instancia.nome, "quantidade_total": 0}
            estoque_total[chave_produto]["quantidade_total"] += prod_instancia.quantidade
    
    vendas = sorted([v.to_dict() for v in Venda.listar_todas()], key=lambda x: x['data_hora'], reverse=True)

    dias_alerta_antecedencia = 7 
    data_hoje_obj = date.today()
    limite_alerta = data_hoje_obj + timedelta(days=dias_alerta_antecedencia)
    produtos_alerta_validade = []

    for area_obj in AreaArmazem.listar_todas():
        for produto_obj in area_obj.listar_produtos():
            status_validade = ""
            dias_para_vencer_calc = (produto_obj.data_validade - data_hoje_obj).days

            if produto_obj.data_validade < data_hoje_obj:
                status_validade = "VENCIDO"
            elif produto_obj.data_validade <= limite_alerta:
                status_validade = "PROXIMO_VENCIMENTO"
            
            if status_validade:
                produtos_alerta_validade.append({
                    "area_id": area_obj.id_area,
                    "nome_area": area_obj.nome,
                    "produto": produto_obj.to_dict(),
                    "status_validade": status_validade,
                    "dias_para_vencer": dias_para_vencer_calc
                })
    
    produtos_alerta_validade.sort(key=lambda x: (x["status_validade"] != "VENCIDO", x["dias_para_vencer"]))

    return render_template('relatorios.html', 
                         estoque_total=estoque_total, 
                         vendas_registradas=vendas, 
                         produtos_alerta_validade=produtos_alerta_validade,
                         dias_alerta=dias_alerta_antecedencia)

# --- API Endpoints ---
@app.route('/api/armazem/<id_area>/produtos', methods=['GET'])
@login_necessario(permissao_requerida='visualizar_armazem')
def api_produtos_por_area(id_area):
    area = AreaArmazem.buscar_por_id(id_area)
    if not area:
        return jsonify({"erro": "Área não encontrada"}), 404
    return jsonify(area.to_dict())

@app.route('/api/estoque_geral', methods=['GET'])
@login_necessario(permissao_requerida='gerente')
def api_estoque_geral():
    estoque_completo = [area.to_dict() for area in AreaArmazem.listar_todas()]
    return jsonify(estoque_completo)

# --- Context Processor ---
@app.context_processor
def injetar_dados_globais():
    user_info = None
    if 'username' in session:
        user_info = {
            'username': session.get('username'),
            'funcao': session.get('user_funcao'),
            'nome': session.get('user_nome')
        }
    return dict(usuario_logado=user_info, data_hoje_global=date.today())

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)