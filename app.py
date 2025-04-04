from flask import Flask, render_template, request
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import os

app = Flask(__name__)
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

@app.route("/", methods=["GET", "POST"])
def index():
    client = connect_mongo()
    databases = []
    error_message = None

    if client:
        try:
            databases = client.list_database_names()
        except Exception as e:
            error_message = "No es posible listar las bases de datos."
            print(f"Error al listar bases de datos: {e}")
        finally:
            client.close()

    if request.method == "POST":
        selected_db = request.form.get("database")
        collections_data = get_collections_data(selected_db)
        return render_template("index.html", databases=databases, selected_db=selected_db, collections_data=collections_data, error_message=error_message)

    return render_template("index.html", databases=databases, error_message=error_message)

def get_collections_data(database_name):
    client = connect_mongo()
    collections_data = []
    if client and database_name:
        db = client[database_name]
        try:
            collections = db.list_collection_names()
            for index, collection_name in enumerate(collections):
                count = db[collection_name].count_documents({})
                collections_data.append({"index": index + 1, "name": collection_name, "count": count})
        except Exception as e:
            print(f"Error al obtener colecciones de {database_name}: {e}")
        finally:
            client.close()
    return collections_data

if __name__ == "__main__":
    app.run(debug=True,host="0.0.0.0",port=os.getenv("PORT",default=5000))