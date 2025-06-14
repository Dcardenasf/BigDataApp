from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import zipfile
import os
from datetime import datetime
import json
import re
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
import shutil
import io
import gc


app = Flask(__name__)
app.secret_key ='secretkey88*'

VERSION_APP ="Versión 1.6.0"
CREATOR_APP ="Daniel Mauricio Cardenas"

mongo_uri = os.environ.get("MONGO_URI")

if not mongo_uri:
    uri='mongodb+srv://DbCentral:DbCentral2025@cluster0.le99u.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0'
    mongo_uri = uri

# Función para conectar a MongoDB
def connect_mongo():
    try:
        client = MongoClient(mongo_uri, server_api=ServerApi('1'))
        client.admin.command('ping')
        print("Conexión exitosa a MongoDB!")
        return client
    except Exception as e:
        print(f"Error al conectar a MongoDB: {e}")
        return None
    
# Función para conectar a Elasticsearch

cliente_elasticsearch = Elasticsearch(
    "https://81d5a08a115f4ac6be7e758c4051480d.us-central1.gcp.cloud.es.io:443",
    api_key="czR1cE9KY0JUdlJ0NFZoUnl6RmY6eTRFVHREek5YRjdPU3hjNW5ScGs3QQ=="
)
INDEX_NAME = "ucentral_dmcf"


@app.route('/')
def index():
    return render_template('index.html',version=VERSION_APP, creador=CREATOR_APP)
@app.route('/about')
def about():
    return render_template('about.html', version=VERSION_APP,creador=CREATOR_APP)

@app.route("/contacto", methods=["GET", "POST"])
def contacto():
    if request.method == 'POST':
        client = connect_mongo()
        if not client:
            return render_template('login.html', error_message='Error de conexión con la base de datos. Por favor, intente más tarde.', version=VERSION_APP,creador=CREATOR_APP)
        try:
            db = client['administracion']
            security_collection = db['contacto']
            nombre = request.form.get('nombre')
            email = request.form.get('email')
            asunto = request.form.get('asunto')
            mensaje = request.form.get('mensaje')
            fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Guardar el mensaje en la base de datos
            security_collection.insert_one({
                'nombre': nombre,
                'email': email,
                'asunto': asunto,
                'mensaje': mensaje,
                'fecha': fecha
            })
            return render_template('contacto.html', success_message='Mensaje enviado con éxito', version=VERSION_APP,creador=CREATOR_APP)
        except Exception as e:
            return render_template('contacto.html', error_message=f'Error al enviar el mensaje: {str(e)}', version=VERSION_APP,creador=CREATOR_APP)
        finally:
            client.close()  
    return render_template('contacto.html',version=VERSION_APP,creador=CREATOR_APP)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Primero verificar la conectividad con MongoDB
        client = connect_mongo()
        if not client:
            return render_template('login.html', error_message='Error de conexión con la base de datos. Por favor, intente más tarde.', version=VERSION_APP,creador=CREATOR_APP)
        
        try:
            db = client['administracion']
            security_collection = db['seguridad']
            usuario = request.form['usuario']
            password = request.form['password']
            
            # Verificar credenciales en MongoDB
            user = security_collection.find_one({
                'usuario': usuario,
                'password': password
            })
            
            if user:
                session['usuario'] = usuario
                return redirect(url_for('gestion_proyecto'))
            else:
                return render_template('login.html', error_message='Usuario o contraseña incorrectos', version=VERSION_APP,creador=CREATOR_APP)
        except Exception as e:
            return render_template('login.html', error_message=f'Error al validar credenciales: {str(e)}', version=VERSION_APP,creador=CREATOR_APP)
        finally:
            client.close()
    
    return render_template('login.html', version=VERSION_APP,creador=CREATOR_APP)


@app.route('/gestion_proyecto', methods=['GET', 'POST'])
def gestion_proyecto():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    try:
        client = connect_mongo()
        # Obtener lista de bases de datos
        databases = client.list_database_names()
        # Eliminar bases de datos del sistema
        system_dbs = ['admin', 'local', 'config']
        databases = [db for db in databases if db not in system_dbs]
        
        selected_db = request.form.get('database') if request.method == 'POST' else request.args.get('database')
        collections_data = []
        
        if selected_db:
            db = client[selected_db]
            collections = db.list_collection_names()
            for index, collection_name in enumerate(collections, 1):
                collection = db[collection_name]
                count = collection.count_documents({})
                collections_data.append({
                    'index': index,
                    'name': collection_name,
                    'count': count
                })
        
        return render_template('gestion/index.html',
                            databases=databases,
                            selected_db=selected_db,
                            collections_data=collections_data,
                            version=VERSION_APP,
                            creador=CREATOR_APP,
                            usuario=session['usuario'])
    except Exception as e:
        return render_template('gestion/index.html',
                            error_message=f'Error al conectar con MongoDB: {str(e)}',
                            version=VERSION_APP,
                            creador=CREATOR_APP,
                            usuario=session['usuario'])

@app.route('/listar-usuarios')
def listar_usuarios():
    try:
        client = connect_mongo()
        if not client:
            return jsonify({'error': 'Error de conexión con la base de datos'}), 500
        
        db = client['administracion']
        security_collection = db['seguridad']
        
        # Obtener todos los usuarios, excluyendo la contraseña por seguridad
        #usuarios = list(security_collection.find({}, {'password': 0}))

        usuarios = list(security_collection.find())
        
        # Convertir ObjectId a string para serialización JSON
        for usuario in usuarios:
            usuario['_id'] = str(usuario['_id'])
        
        return jsonify(usuarios)
    except Exception as e:
        return jsonify({'error': f'Error en la API de búsqueda en la ruta "/api/search": {str(e)}'}), 500
    finally:
        if 'client' in locals():
            client.close()

@app.route('/crear-coleccion-form/<database>')
def crear_coleccion_form(database):
    if 'usuario' not in session:
        return redirect(url_for('login'))
    return render_template('gestion/crear_coleccion.html', 
                         database=database,
                         usuario=session['usuario'],
                         version=VERSION_APP,
                         creador=CREATOR_APP)

@app.route('/crear-coleccion', methods=['POST'])
def crear_coleccion():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    try:
        database = request.form.get('database')
        collection_name = request.form.get('collection_name')
        zip_file = request.files.get('zip_file')
        
        if not all([database, collection_name, zip_file]):
            return render_template('gestion/crear_coleccion.html',
                                error_message='Todos los campos son requeridos',
                                database=database,
                                usuario=session['usuario'],
                                version=VERSION_APP,
                                creador=CREATOR_APP)
        
        # Conectar a MongoDB
        client = connect_mongo()
        if not client:
            return render_template('gestion/crear_coleccion.html',
                                error_message='Error de conexión con MongoDB',
                                database=database,
                                usuario=session['usuario'],
                                version=VERSION_APP,
                                creador=CREATOR_APP)
        
        # Crear la colección
        db = client[database]
        collection = db[collection_name]
        
        # Procesar el archivo ZIP
        with zipfile.ZipFile(zip_file) as zip_ref:
            # Extraer todos los archivos JSON del ZIP
            for file_info in zip_ref.infolist():
                if file_info.filename.endswith('.json'):
                    with zip_ref.open(file_info.filename) as f:
                        try:
                            json_data = json.load(io.TextIOWrapper(f, encoding='utf-8'))

                            if isinstance(json_data, list):
                                # Insertar documentos en lotes
                                for i in range(0, len(json_data), 100):
                                    batch = json_data[i:i+100]
                                    try:
                                        collection.insert_many(batch)
                                    except Exception as e:
                                        print(f"Error al insertar lote: {str(e)}")
                            else:
                                # Insertar un único documento
                                collection.insert_one(json_data)
                        except json.JSONDecodeError:
                            print(f"Error al decodificar JSON en el archivo {file_info.filename}")
                        except Exception as e:
                            print(f"Error al procesar el archivo {file_info.filename}: {str(e)}")
                        finally:
                            del json_data
                            gc.collect()
        return redirect(url_for('gestion_proyecto', database=database))   
    
    except Exception as e:
        return render_template('gestion/crear_coleccion.html',
                            error_message=f'Error al crear la colección: {str(e)}',
                            database=database,
                            usuario=session['usuario'],
                            version=VERSION_APP,
                            creador=CREATOR_APP)
    finally:
        if 'client' in locals():
            client.close()

@app.route('/ver-registros/<database>/<collection>')
def ver_registros(database, collection):
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    try:
        client = connect_mongo()
        if not client:
            return render_template('gestion/index.html',
                                error_message='Error de conexión con MongoDB',
                                version=VERSION_APP,
                                creador=CREATOR_APP,
                                usuario=session['usuario'])
        
        db = client[database]
        collection_obj = db[collection]
        
        # Obtener los primeros 100 registros por defecto
        records = list(collection_obj.find().limit(100))
        
        # Convertir ObjectId a string para serialización JSON
        for record in records:
            record['_id'] = str(record['_id'])
        
        return render_template('gestion/ver_registros.html',
                            database=database,
                            collection_name=collection,
                            records=records,
                            version=VERSION_APP,
                            creador=CREATOR_APP,
                            usuario=session['usuario'])
    except Exception as e:
        return render_template('gestion/index.html',
                            error_message=f'Error al obtener registros: {str(e)}',
                            version=VERSION_APP,
                            creador=CREATOR_APP,
                            usuario=session['usuario'])
    finally:
        if 'client' in locals():
            client.close()

@app.route('/obtener-registros', methods=['POST'])
def obtener_registros():
    if 'usuario' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        database = request.form.get('database')
        collection = request.form.get('collection')
        limit = int(request.form.get('limit', 100))
        
        client = connect_mongo()
        if not client:
            return jsonify({'error': 'Error de conexión con MongoDB'}), 500
        
        db = client[database]
        collection_obj = db[collection]
        
        # Obtener los registros con el límite especificado
        records = list(collection_obj.find().limit(limit))
        
        # Convertir ObjectId a string para serialización JSON
        for record in records:
            record['_id'] = str(record['_id'])
        
        return jsonify({'records': records})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'client' in locals():
            client.close()

@app.route('/crear-base-datos-form')
def crear_base_datos_form():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    return render_template('gestion/crear_base_datos.html',
                         version=VERSION_APP,
                         creador=CREATOR_APP,
                         usuario=session['usuario'])

@app.route('/crear-base-datos', methods=['POST'])
def crear_base_datos():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    try:
        database_name = request.form.get('database_name')
        collection_name = request.form.get('collection_name')
        
        # Validar que los nombres no contengan caracteres especiales
        valid_pattern = re.compile(r'^[a-zA-Z0-9_]+$')
        if not valid_pattern.match(database_name) or not valid_pattern.match(collection_name):
            return render_template('gestion/crear_base_datos.html',
                                error_message='Los nombres no pueden contener tildes, espacios ni caracteres especiales',
                                version=VERSION_APP,
                                creador=CREATOR_APP,
                                usuario=session['usuario'])
        
        # Conectar a MongoDB
        client = connect_mongo()
        if not client:
            return render_template('gestion/crear_base_datos.html',
                                error_message='Error de conexión con MongoDB',
                                version=VERSION_APP,
                                creador=CREATOR_APP,
                                usuario=session['usuario'])
        
        # Crear la base de datos y la colección
        db = client[database_name]
        collection = db[collection_name]
        
        # Insertar un documento vacío para crear la colección
        collection.insert_one({})
        
        # Eliminar el documento vacío
        collection.delete_one({})
        
        return redirect(url_for('gestion_proyecto', database=database_name))
        
    except Exception as e:
        return render_template('gestion/crear_base_datos.html',
                            error_message=f'Error al crear la base de datos: {str(e)}',
                            version=VERSION_APP,
                            creador=CREATOR_APP,
                            usuario=session['usuario'])
    finally:
        if 'client' in locals():
            client.close()


@app.route('/logout')
def logout():
    # Limpiar todas las variables de sesión
    session.clear()
    # Redirigir al index principal
    return redirect(url_for('index'))

@app.route('/elasticAdmin')
def elasticAdmin():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    try:
        # Obtener información del índice
        index_info = cliente_elasticsearch.indices.get(index=INDEX_NAME)
        doc_count = cliente_elasticsearch.count(index=INDEX_NAME)['count']
        
        return render_template('gestion/ver_elasticAdmin.html',
                            index_name=INDEX_NAME,
                            doc_count=doc_count,
                            version=VERSION_APP,
                            creador=CREATOR_APP,
                            usuario=session['usuario'])
    except Exception as e:
        return render_template('gestion/ver_elasticAdmin.html',
                            error_message=f'Error al conectar con Elasticsearch: {str(e)}',
                            version=VERSION_APP,
                            creador=CREATOR_APP,
                            usuario=session['usuario'])

@app.route('/elastic-agregar-documentos', methods=['GET', 'POST'])
def elastic_agregar_documentos():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            if 'zipFile' not in request.files:
                return render_template('gestion/elastic_agregar_documentos.html',
                                    error_message='No se ha seleccionado ningún archivo',
                                    index_name=INDEX_NAME,
                                    version=VERSION_APP,
                                    creador=CREATOR_APP,
                                    usuario=session['usuario'])
            
            zip_file = request.files['zipFile']
            if zip_file.filename == '':
                return render_template('gestion/elastic_agregar_documentos.html',
                                    error_message='No se ha seleccionado ningún archivo',
                                    index_name=INDEX_NAME,
                                    version=VERSION_APP,
                                    creador=CREATOR_APP,
                                    usuario=session['usuario'])
            
            # Crear directorio temporal
            temp_dir = os.path.join(os.path.dirname(__file__), 'temp')
            # LIMPIEZA DEL TEMPORAL ANTES DE USARLO
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            os.makedirs(temp_dir, exist_ok=True)
            # Guardar y extraer el archivo ZIP
            zip_path = os.path.join(temp_dir, zip_file.filename)
            zip_file.save(zip_path)
            with zipfile.ZipFile(zip_path) as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Procesar archivos JSON
            success_count = 0
            error_count = 0
            
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    if file.endswith('.json'):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                json_data = json.load(f)
                                docs = json_data if isinstance(json_data, list) else [json_data]
                                # Insertar en lotes de 100 usando bulk
                                for i in range(0, len(docs), 100):
                                    batch = docs[i:i+100]
                                    actions = [
                                        {"_index": INDEX_NAME, "_source": doc}
                                        for doc in batch
                                    ]
                                    success, _ = bulk(cliente_elasticsearch, actions)
                                    success_count += success
                        except Exception as e:
                            error_count += 1
                            print(f"Error procesando {file}: {str(e)}")
            
            # Limpiar archivos temporales
            for root, dirs, files in os.walk(temp_dir, topdown=False):
                for file in files:
                    os.remove(os.path.join(root, file))
                for dir in dirs:
                    os.rmdir(os.path.join(root, dir))
            os.rmdir(temp_dir)
            
            return render_template('gestion/elastic_agregar_documentos.html',
                                success_message=f'Se indexaron {success_count} documentos exitosamente. Errores: {error_count}',
                                index_name=INDEX_NAME,
                                version=VERSION_APP,
                                creador=CREATOR_APP,
                                usuario=session['usuario'])
            
        except Exception as e:
            return render_template('gestion/elastic_agregar_documentos.html',
                                error_message=f'Error al procesar el archivo: {str(e)}',
                                index_name=INDEX_NAME,
                                version=VERSION_APP,
                                creador=CREATOR_APP,
                                usuario=session['usuario'])
    
    return render_template('gestion/elastic_agregar_documentos.html',
                         index_name=INDEX_NAME,
                         version=VERSION_APP,
                         creador=CREATOR_APP,
                         usuario=session['usuario'])

@app.route('/elastic-listar-documentos')
def elastic_listar_documentos():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    try:
        # Obtener los primeros 100 documentos
        response = cliente_elasticsearch.search(
            index=INDEX_NAME,
            body={
                "query": {"match_all": {}},
                "size": 100
            }
        )
        
        documents = response['hits']['hits']
        
        return render_template('gestion/elastic_listar_documentos.html',
                            index_name=INDEX_NAME,
                            documents=documents,
                            version=VERSION_APP,
                            creador=CREATOR_APP,
                            usuario=session['usuario'])
    except Exception as e:
        return render_template('gestion/elastic_listar_documentos.html',
                            error_message=f'Error al obtener documentos: {str(e)}',
                            index_name=INDEX_NAME,
                            version=VERSION_APP,
                            creador=CREATOR_APP,
                            usuario=session['usuario'])

@app.route('/elastic-eliminar-documento', methods=['POST'])
def elastic_eliminar_documento():
    if 'usuario' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        doc_id = request.form.get('doc_id')
        if not doc_id:
            return jsonify({'error': 'ID de documento no proporcionado'}), 400

        response = cliente_elasticsearch.delete(index=INDEX_NAME, id=doc_id)

        if response['result'] == 'deleted':
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Error al eliminar el documento'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/buscador', methods=['GET', 'POST'])
def buscador():
    try:
        # Obtener parámetros de paginación
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 50))
        from_ = (page - 1) * page_size

        if request.method == 'POST':
            search_type = request.form.get('search_type')
            search_text = request.form.get('search_text')
            fecha_desde = request.form.get('fecha_desde')
            fecha_hasta = request.form.get('fecha_hasta')

            if not fecha_desde:
                fecha_desde = "1900-01-01"
            if not fecha_hasta:
                fecha_hasta = datetime.now().strftime("%Y-%m-%d")

            query = {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "match": {
                                    search_type: search_text
                                }
                            },
                            {
                                "range": {
                                    "Release Date": {
                                        "format": "yyyy-MM-dd",
                                        "gte": fecha_desde,
                                        "lte": fecha_hasta
                                    }
                                }
                            }
                        ]
                    }
                },
                "from": from_,
                "size": page_size
            }

            response = cliente_elasticsearch.search(
                index=INDEX_NAME,
                body=query
            )

            hits = response['hits']['hits']
            total = response['hits']['total']['value']

            return render_template('buscador.html',
                                   version=VERSION_APP,
                                   creador=CREATOR_APP,
                                   hits=hits,
                                   total=total,
                                   page=page,
                                   page_size=page_size,
                                   search_type=search_type,
                                   search_text=search_text,
                                   fecha_desde=fecha_desde,
                                   fecha_hasta=fecha_hasta,
                                   query=query)
        else:
            # GET: solo renderiza el formulario vacío
            return render_template('buscador.html',
                                   version=VERSION_APP,
                                   creador=CREATOR_APP,
                                   page=page,
                                   page_size=page_size)
    except Exception as e:
        return render_template('buscador.html',
                               version=VERSION_APP,
                               creador=CREATOR_APP,
                               error_message=f'Error en la búsqueda en la ruta \"/buscador\": {str(e)}')

@app.route('/api/search', methods=['POST'])
def search():
    try:
        data = request.get_json()
        index_name = data.get('index', os.getenv('ELASTIC_INDEX_NAME', 'ucentral_dmcf'))
        query = data.get('query')
        if not isinstance(query, dict):
            return jsonify({'error': 'Invalid query format. Query must be a dictionary.'}), 400

        # Ejecutar la búsqueda en Elasticsearch
        response = cliente_elasticsearch.search(
            index=index_name,
            body=query
        )
        sanitized_response = {
            'hits': response.get('hits', {}).get('hits', []),
            'total': response.get('hits', {}).get('total', {}).get('value', 0)
        }
        return jsonify(sanitized_response)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True,host="0.0.0.0",port=os.getenv("PORT",default=5000))