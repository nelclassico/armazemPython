# laticinios_armazem/app.py

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime, timedelta, date # date importado aqui
import functools # Para o decorator de login
import logging # Para logging

# Importar modelos e funções do models.py
from models import (
    Usuario, ProdutoLacteo, AreaArmazem, Venda,
    db_usuarios, db_areas_armazem, db_vendas_registradas, db_produtos_catalogo,
    get_produto_catalogo_por_id, popular_dados_iniciais # popular_dados_iniciais é importado
)

app = Flask(__name__)
app.secret_key = 'chave_secreta_para_sessoes_flask_laticinios_minerva' # Mude isso em um ambiente de produção!

# Configurar logging básico
logging.basicConfig(level=logging.DEBUG)

# Assegura que os dados iniciais sejam carregados (se ainda não foram)
# A lógica em models.py já tenta fazer isso na importação inicial.
if not db_usuarios and not db_areas_armazem: # Verifica se os dicionários estão vazios
     app.logger.info("Populando dados iniciais pois o banco em memória está vazio.")
     popular_dados_iniciais()

# --- Autenticação e Controle de Acesso ---
def login_necessario(permissao_requerida: str = None):
    """
    Decorator para verificar se o usuário está logado e, opcionalmente,
    se tem uma permissão específica.
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(*args, **kwargs):
            if 'username' not in session:
                flash("Por favor, faça login para acessar esta página.", "warning")
                return redirect(url_for('login', next=request.url))
            
            usuario_logado = Usuario.buscar_por_username(session['username'])
            if not usuario_logado: # Caso a sessão exista mas o usuário foi removido do DB
                session.clear()
                flash("Sua sessão é inválida. Por favor, faça login novamente.", "danger")
                return redirect(url_for('login'))

            # Adiciona o objeto usuario_logado ao contexto da requisição para fácil acesso na view, se necessário
            # g.user = usuario_logado # Se fosse usar flask.g

            if permissao_requerida and not usuario_logado.tem_permissao(permissao_requerida):
                flash("Você não tem permissão para realizar esta ação ou acessar esta página.", "danger")
                # Redireciona para a página anterior ou para a página inicial do armazém
                return redirect(request.referrer or url_for('pagina_inicial_armazem')) 
            
            return view_func(*args, **kwargs)
        return wrapper
    return decorator

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        senha = request.form.get('password')
        usuario = Usuario.buscar_por_username(username) # Busca o usuário pelo username

        if usuario and usuario.verificar_senha(senha): # Verifica a senha
            session['username'] = usuario.username
            session['user_funcao'] = usuario.funcao
            session['user_nome_completo'] = usuario.nome_completo # Usa nome_completo
            flash(f"Login bem-sucedido! Bem-vindo(a), {usuario.nome_completo}.", "success")
            
            next_url = request.args.get('next')
            return redirect(next_url or url_for('pagina_inicial_armazem')) # Redireciona para pagina_inicial_armazem
        else:
            flash("Usuário ou senha inválidos. Tente novamente.", "danger")
    
    if 'username' in session: # Se já estiver logado, redireciona para o armazém
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
def index_redirect(): # Nome da função para o endpoint '/'
    return redirect(url_for('pagina_inicial_armazem'))

@app.route('/armazem')
@login_necessario(permissao_requerida='visualizar_armazem')
def pagina_inicial_armazem(): # Nome da função para o endpoint '/armazem'
    """Exibe a visão geral do armazém com suas áreas."""
    areas = AreaArmazem.listar_todas() # Usa o método estático da classe AreaArmazem
    return render_template('armazem.html', areas=areas)

@app.route('/armazem/<id_area>')
@login_necessario(permissao_requerida='detalhes_area')
def detalhes_da_area(id_area): # Nome da função consistente
    """Exibe os detalhes dos produtos em uma área específica."""
    area = AreaArmazem.buscar_por_id(id_area) # Usa o método estático
    if not area:
        flash(f"Área com ID '{id_area}' não encontrada.", "danger")
        return redirect(url_for('pagina_inicial_armazem'))
    
    # Ordena os produtos por data de validade para melhor visualização
    produtos_na_area = sorted(area.listar_produtos_objetos(), key=lambda p: p.data_validade)
    
    return render_template('area_detalhes.html', 
                           area=area, 
                           produtos=produtos_na_area,
                           produtos_catalogo=db_produtos_catalogo, # Para o formulário de adicionar
                           data_hoje=date.today()) # Passa data_hoje para o template

@app.route('/armazem/<id_area>/adicionar_produto', methods=['POST'])
@login_necessario(permissao_requerida='gerente') # Apenas gerentes podem adicionar produtos
def adicionar_produto_na_area(id_area):
    area = AreaArmazem.buscar_por_id(id_area)
    if not area:
        flash(f"Área '{id_area}' não encontrada.", "danger")
        return redirect(url_for('pagina_inicial_armazem'))

    try:
        id_catalogo_produto = request.form.get('id_catalogo_produto')
        quantidade_str = request.form.get('quantidade')
        data_validade_str = request.form.get('data_validade') # Nome consistente com o ProdutoLacteo
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
            nome_produto=produto_do_catalogo['nome'], # nome_produto
            quantidade=quantidade,
            data_validade_str=data_validade_str, # data_validade_str
            lote=lote.strip().upper() # Padroniza o lote
        )
        area.adicionar_produto(novo_produto)
        flash(f"Produto '{novo_produto.nome_produto}' (Lote: {novo_produto.lote}) adicionado/atualizado com sucesso na área {area.nome}!", "success")
    
    except ValueError as e: # Captura ValueError do construtor de ProdutoLacteo ou int()
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
        # O formulário no template area_detalhes.html envia 'id_instancia_produto_venda'
        id_instancia_produto_venda = request.form.get('id_instancia_produto_venda')
        quantidade_venda_str = request.form.get('quantidade_venda')
        destino_venda = request.form.get('destino_venda')

        if not all([id_instancia_produto_venda, quantidade_venda_str, destino_venda]):
            flash("Informações insuficientes para registrar a venda (ID do produto, quantidade ou destino faltando).", "warning")
            return redirect(url_for('detalhes_da_area', id_area=id_area))
        
        quantidade_venda = int(quantidade_venda_str)
        if quantidade_venda <= 0:
            flash("A quantidade para venda deve ser positiva.", "warning")
            return redirect(url_for('detalhes_da_area', id_area=id_area))

        # Busca o produto pelo seu ID de instância (id_catalogo-lote-data_validade)
        produto_para_venda = area.produtos.get(id_instancia_produto_venda)

        if not produto_para_venda:
            flash(f"Produto com ID de instância '{id_instancia_produto_venda}' não encontrado nesta área.", "danger")
            return redirect(url_for('detalhes_da_area', id_area=id_area))

        if produto_para_venda.quantidade < quantidade_venda:
            flash(f"Quantidade insuficiente em estoque para '{produto_para_venda.nome_produto}' (Lote: {produto_para_venda.lote}). Disponível: {produto_para_venda.quantidade}", "warning")
            return redirect(url_for('detalhes_da_area', id_area=id_area))

        # Tenta remover o produto do estoque da área
        sucesso_remocao = area.remover_produto(id_instancia_produto_venda, quantidade_venda)

        if sucesso_remocao:
            nova_venda = Venda(
                id_catalogo_produto=produto_para_venda.id_catalogo_produto,
                nome_produto=produto_para_venda.nome_produto,
                lote=produto_para_venda.lote,
                data_validade_produto=produto_para_venda.data_validade.strftime('%Y-%m-%d'), # Data de validade do produto
                quantidade_vendida=quantidade_venda,
                destino=destino_venda,
                area_origem_id=id_area,
                usuario_responsavel=session['username'] # Registra o usuário que fez a venda
            )
            Venda.registrar(nova_venda) # Usa o método estático da classe Venda
            flash(f"Venda de {quantidade_venda} unidade(s) de '{produto_para_venda.nome_produto}' (Lote: {produto_para_venda.lote}) registrada com sucesso!", "success")
        else:
            # Esta condição pode ser redundante devido às verificações anteriores, mas é uma salvaguarda.
            flash(f"Falha ao tentar vender {quantidade_venda} unidade(s) de '{produto_para_venda.nome_produto}'. Verifique o estoque.", "danger")
    
    except ValueError: # Erro na conversão de quantidade_venda para int
        flash("Quantidade para venda inválida. Deve ser um número.", "danger")
    except Exception as e:
        app.logger.error(f"Erro inesperado ao vender produto da área {id_area}: {e}", exc_info=True)
        flash("Ocorreu um erro inesperado ao processar a venda.", "danger")

    return redirect(url_for('detalhes_da_area', id_area=id_area))


@app.route('/relatorios')
@login_necessario(permissao_requerida='gerente') # Apenas gerentes podem ver relatórios
def pagina_relatorios(): # Nome da função consistente
    # 1. Estoque Atual por Produto (agregado)
    estoque_agregado = {}
    # todos_os_produtos_em_estoque = [] # Não usado diretamente, mas a lógica abaixo é mais eficiente
    for area_obj in AreaArmazem.listar_todas():
        for prod_instancia in area_obj.listar_produtos_objetos():
            # todos_os_produtos_em_estoque.append(prod_instancia) # Desnecessário se agregando
            chave_produto = prod_instancia.id_catalogo_produto 
            if chave_produto not in estoque_agregado:
                estoque_agregado[chave_produto] = {"nome": prod_instancia.nome_produto, "quantidade_total": 0}
            estoque_agregado[chave_produto]["quantidade_total"] += prod_instancia.quantidade
    
    # 2. Produtos Vendidos (ordenados por data, mais recentes primeiro)
    vendas = sorted([v.to_dict() for v in Venda.listar_todas()], key=lambda x: x['data_hora'], reverse=True)

    # 3. Alertas de Validade (produtos vencendo nos próximos X dias ou já vencidos)
    dias_alerta_antecedencia = 7 
    data_hoje_obj = date.today() # Objeto date
    limite_alerta = data_hoje_obj + timedelta(days=dias_alerta_antecedencia)
    produtos_alerta_validade = []

    for area_obj in AreaArmazem.listar_todas():
        for produto_obj in area_obj.listar_produtos_objetos(): # produto_obj é uma instância de ProdutoLacteo
            status_validade = ""
            dias_para_vencer_calc = (produto_obj.data_validade - data_hoje_obj).days

            if produto_obj.data_validade < data_hoje_obj: # Já venceu
                status_validade = "VENCIDO"
            elif produto_obj.data_validade <= limite_alerta: # Próximo do vencimento (inclui hoje se <= limite_alerta)
                status_validade = "PROXIMO_VENCIMENTO"
            
            if status_validade: # Adiciona à lista apenas se houver um status de alerta
                produtos_alerta_validade.append({
                    "area_id": area_obj.id_area,
                    "nome_area": area_obj.nome,
                    "produto": produto_obj.to_dict(), # Converte o objeto produto para dict
                    "status_validade": status_validade,
                    "dias_para_vencer": dias_para_vencer_calc
                })
    
    # Ordenar alertas: vencidos primeiro, depois por proximidade de vencimento (menor dias_para_vencer)
    produtos_alerta_validade.sort(key=lambda x: (x["status_validade"] != "VENCIDO", x["dias_para_vencer"]))


    return render_template('relatorios.html', 
                           estoque_agregado=estoque_agregado, 
                           vendas_registradas=vendas, 
                           produtos_alerta_validade=produtos_alerta_validade,
                           dias_alerta=dias_alerta_antecedencia)

# --- API Endpoints (Exemplo para integração futura) ---
@app.route('/api/armazem/<id_area>/produtos', methods=['GET'])
@login_necessario(permissao_requerida='visualizar_armazem') # Proteger a API
def api_produtos_por_area(id_area): # Nome da função consistente
    area = AreaArmazem.buscar_por_id(id_area)
    if not area:
        return jsonify({"erro": "Área não encontrada"}), 404
    return jsonify(area.to_dict()) # Usa o método to_dict da classe AreaArmazem

@app.route('/api/estoque_geral', methods=['GET'])
@login_necessario(permissao_requerida='gerente') # Apenas gerentes
def api_estoque_geral(): # Nome da função consistente
    estoque_completo = [area.to_dict() for area in AreaArmazem.listar_todas()]
    return jsonify(estoque_completo)

# --- Context Processor para injetar dados globais nos templates ---
@app.context_processor
def injetar_dados_globais(): # Nome da função consistente
    """Injeta informações do usuário logado e outras utilidades em todos os templates."""
    user_info = None
    if 'username' in session:
        # Busca o usuário para garantir que os dados da sessão (funcao, nome) estão atualizados
        # Isso é opcional se você confia que a sessão não ficará dessincronizada.
        # usuario_atual = Usuario.buscar_por_username(session['username'])
        # if usuario_atual:
        #     user_info = {
        #         'username': usuario_atual.username,
        #         'funcao': usuario_atual.funcao,
        #         'nome_completo': usuario_atual.nome_completo
        #     }
        # else: # Se o usuário não for encontrado, limpa a sessão para evitar problemas
        #     session.clear()
        # Simplificado para usar diretamente da sessão, assumindo que é atualizado no login:
        user_info = {
            'username': session.get('username'),
            'funcao': session.get('user_funcao'),
            'nome_completo': session.get('user_nome_completo')
        }

    return dict(usuario_logado=user_info, data_hoje_global=date.today())


if __name__ == '__main__':
    # app.run(debug=True) # Executa o servidor Flask em modo de desenvolvimento
    app.run(debug=True, host='0.0.0.0', port=5001) # Permite acesso na rede local
