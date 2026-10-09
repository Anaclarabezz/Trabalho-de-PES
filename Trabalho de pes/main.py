from flask import Flask, render_template, request, redirect, session
from database import get_db_connection

app = Flask(__name__)

app.secret_key = 'senhasecreta'


@app.route('/')
def index():
    return render_template('menu.html', titulo="Hotel ByGirls")

@app.route('/usuario', methods=['GET', 'POST'])
def usuario():

    if request.method == 'POST':

        nome = request.form['nome'].strip()
        cpf = request.form['cpf'].strip()
        telefone = request.form['telefone'].strip()
        email = request.form['email'].strip()
        senha = request.form['senha']

        conn = get_db_connection()
        cursor = conn.cursor()

        try:

            cursor.execute("""
                INSERT INTO usuario
                (nome, cpf, telefone, email, senha)
                VALUES (%s,%s,%s,%s,%s)
            """,(nome, cpf, telefone, email, senha))

            conn.commit()

            mensagem = "Usuário cadastrado com sucesso!"

        except Exception as e:

            conn.rollback()
            mensagem = f"Erro: {e}"

        finally:

            conn.close()

        return render_template(
            "usuario.html",
            mensagem_sucesso=mensagem
        )

    return render_template("usuario.html")

@app.route('/loginusuario', methods=['GET','POST'])
def login():

    if request.method == 'POST':

        email = request.form['email']
        senha = request.form['senha']

        conn = get_db_connection()

        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT *
            FROM usuario
            WHERE email=%s AND senha=%s
        """,
        (email, senha))

        usuario = cursor.fetchone()

        conn.close()

        if usuario:
            session['usuario'] = usuario['nome']
            session['idUsuario'] = usuario['idUsuario']
            session['tipo'] = usuario['tipo']
            return redirect('/')

        else:

            return render_template(
                'loginusuario.html',
                mensagem_erro="E-mail ou senha inválidos."
            )

    return render_template("loginusuario.html")

# Rota para cadastro de reserva
@app.route('/cadreserva', methods=['GET', 'POST'])
def cadreserva():

    if 'usuario' not in session:
        return redirect('/login')

    id_usuario = session['idUsuario']


    if request.method == 'POST':

        checkin = request.form['checkin']
        checkout = request.form['checkout']
        hospedes = request.form['hospedes']
        criancas = request.form.get('criancas', 0)
        quarto = request.form['tipoquarto']
        valorDiaria = request.form['valorDiaria']
        valorTotal = request.form['valorTotal']
        observacoes = request.form.get('observacoes','')
        metododepagamento = request.form.get('metododepagamento')

        conn = get_db_connection()
        cursor = conn.cursor()

        try:

            cursor.execute("""
                INSERT INTO reserva
                (idUsuario, checkin, checkout, hospedes,criancas, quarto, valorDiaria, valorTotal, observacoes, metododepagamento)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
            id_usuario,
            checkin,
            checkout,
            hospedes,
            criancas,
            quarto,
            valorDiaria,
            valorTotal,
            observacoes,
            metododepagamento
            ))


            conn.commit()

            mensagem="Reserva cadastrada com sucesso!"


        except Exception as e:

            conn.rollback()

            mensagem=f"Erro: {e}"


        finally:

            conn.close()


            return render_template(
                "cadreserva.html",
                mensagem_sucesso=mensagem
            )

    return render_template("cadreserva.html")


@app.route('/consultareserva')
def consultareserva():
    # 1. Trava de segurança: verificar se está logado
    if 'usuario' not in session:
        return redirect('/loginusuario')

    # 2. Pegar o ID do usuário que fez o login
    id_usuario_logado = session['idUsuario']

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 3. Adicionar o filtro de usuário (AND r.idUsuario = %s) na query
        cursor.execute("""
            SELECT
                u.nome,
                r.IdReserva AS idReserva,
                r.checkin,
                r.checkout,
                r.hospedes,
                r.quarto,
                r.observacoes,
                r.metododepagamento,
                r.cancelada
            FROM reserva r
            INNER JOIN usuario u
                ON r.idUsuario = u.idUsuario
            WHERE (r.cancelada = 0 OR r.cancelada IS NULL)
              AND r.idUsuario = %s
            ORDER BY r.checkin
        """, (id_usuario_logado,))  # Passando o ID para a query

        reservas = cursor.fetchall()
        conn.close()

        return render_template(
            "consultareserva.html",
            reservas=reservas
        )

    except Exception as e:
        return render_template(
            "consultareserva.html",
            mensagem_erro=str(e)
        )


@app.route('/cancelar_reserva', methods=['POST'])
def cancelar_reserva():
    id_reserva = request.form.get('idReserva')

    print(f"\n[DEBUG] ID da reserva recebido: {id_reserva}")

    if id_reserva:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
            UPDATE reserva 
            SET cancelada = 1, dataCancelamento = CURDATE() 
            WHERE idReserva = %s
            """, (id_reserva,))
            conn.commit()
            print(f"SUCESSO")
        except Exception as e:
            conn.rollback()
            print(f"ERRO")
        finally:
            conn.close()
    else:
        print("[DEBUG] ERRO: O idReserva veio VAZIO do formulário HTML!")

    return redirect('/consultareserva')

@app.route('/preparacao')
def preparacao():
    # Verifica se o usuário está logado
    if 'usuario' not in session:
        return redirect('/loginusuario')
    # Verifica se é administrador
    if session.get('tipo') != 'admin':
        return render_template(
            'preparacao.html',
            acesso_negado=True
        )

    # Pega a data escolhida no formulário
    data_consulta = request.args.get('data')

    # Valores iniciais
    total_reservas = 0
    total_hospedes = 0
    total_criancas = 0
    total_adultos = 0
    reservas = []

    # Só faz a consulta se uma data foi escolhida
    if data_consulta:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            # Consulta o resumo das chegadas
            cursor.execute("""
                SELECT
                    COUNT(*) AS total_reservas,
                    COALESCE(SUM(hospedes), 0) AS total_hospedes,
                    COALESCE(SUM(criancas), 0) AS total_criancas
                FROM reserva
                WHERE checkin = %s
                AND (cancelada = 0 OR cancelada IS NULL)
            """, (data_consulta,))

            resumo = cursor.fetchone()

            total_reservas = resumo['total_reservas']
            total_hospedes = resumo['total_hospedes']
            total_criancas = resumo['total_criancas']

            # Adultos = total de hóspedes - crianças
            total_adultos = total_hospedes - total_criancas

            # Busca os detalhes das reservas
            cursor.execute("""
                SELECT
                    u.nome,
                    r.checkin,
                    r.checkout,
                    r.hospedes,
                    r.criancas,
                    r.quarto,
                    r.observacoes
                FROM reserva r
                INNER JOIN usuario u
                    ON r.idUsuario = u.idUsuario
                WHERE r.checkin = %s
                AND (r.cancelada = 0 OR r.cancelada IS NULL)
                ORDER BY u.nome
            """, (data_consulta,))

            reservas = cursor.fetchall()

        except Exception as e:
            conn.close()

            return render_template(
                'preparacao.html',
                data_consulta=data_consulta,
                total_reservas=0,
                total_hospedes=0,
                total_criancas=0,
                total_adultos=0,
                reservas=[],
                mensagem_erro=f"Erro ao consultar as reservas: {e}"
            )

        finally:
            try:
                conn.close()
            except:
                pass

    return render_template(
        'preparacao.html',
        data_consulta=data_consulta,
        total_reservas=total_reservas,
        total_hospedes=total_hospedes,
        total_criancas=total_criancas,
        total_adultos=total_adultos,
        reservas=reservas
    )

@app.route('/logout')
def logout():

    session.clear()

    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)

# Ponto de entrada da aplicação
if __name__ == '__main__':
    # Inicia o servidor Flask em modo de desenvolvimento
    app.run(debug=True)
