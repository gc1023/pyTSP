from threading import Lock
from flask import Flask, render_template, session, request
from flask_socketio import emit, SocketIO
from json import load
from os import environ
from os.path import abspath, dirname, join
from sqlalchemy import exc as sql_exception
from sys import dont_write_bytecode, path

# prevent python from writing *.pyc files / __pycache__ folders
dont_write_bytecode = True

path_app = dirname(abspath(__file__))
if path_app not in path:
    path.append(path_app)

from database import db, create_database
from models import City
from genetic_algorithm import GeneticAlgorithm

def configure_database(app):
    create_database()
    @app.teardown_request
    def shutdown_session(exception=None):
        db.session.remove()
    db.init_app(app)

def configure_socket(app):
    async_mode, thread = None, None
    socketio = SocketIO(app, async_mode=async_mode)
    thread_lock = Lock()
    return socketio
    
# import data
def import_cities():
    with open(join(path_app, 'data', 'cities.json')) as data:    
        for city_dict in load(data):
            if int(city_dict['population']) < 500000:
                continue
            city = City(**city_dict)
            db.session.add(city)
        try:
            db.session.commit()
        except sql_exception.IntegrityError:
            db.session.rollback()

def create_app(config='config'):
    app = Flask(__name__)
    app.config.from_object('config')

    configure_database(app)
    socketio = configure_socket(app)
    import_cities()
    
    genetic_algorithm = GeneticAlgorithm()
    return app, socketio, genetic_algorithm

app, socketio, genetic_algorithm = create_app()

## Views

@app.route('/')
def index():
    session['best'] = float('inf')
    return render_template(
        'index.html',
        minimum_population = 500000,
        view = '3D',
        cities = {
            city.id: {
                property: getattr(city, property)
                for property in City.properties
                }
            for city in City.query.all()
            },
        async_mode = socketio.async_mode
        )

@socketio.on('send_random')
def emit_random():
    fitness_value, solution = genetic_algorithm.cycle()
    if fitness_value < session['best']:
        session['best'] = fitness_value
        emit('best_solution', solution)
    else:
        emit('current_solution', solution)

if __name__ == '__main__':
    socketio.run(
        app, 
        port = int(environ.get('PORT', 5100))
        )
