from datetime import datetime, timedelta

import pytest

from parking_app.app import create_app
from parking_app.models import Client, ClientParking, Parking, db


@pytest.fixture(scope="session")
def app():
    """Создание приложения для тестирования"""
    app = create_app()
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///test.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    """Тестовый клиент для запросов"""
    return app.test_client()


@pytest.fixture
def db_session(app):
    """Сессия базы данных"""
    with app.app_context():
        yield db


@pytest.fixture
def sample_client(db_session):
    """Создание тестового клиента"""
    client = Client(
        name="Иван",
        surname="Иванов",
        credit_card="1234567812345678",
        car_number="А123БВ777",
    )
    db_session.session.add(client)
    db_session.session.commit()
    return client


@pytest.fixture
def sample_parking(db_session):
    """Создание тестовой парковки"""
    parking = Parking(
        address="ул. Тестовая, д. 1",
        opened=True,
        count_places=10,
        count_available_places=10,
    )
    db_session.session.add(parking)
    db_session.session.commit()
    return parking


@pytest.fixture
def setup_factories(db_session):
    """Настройка фабрик с правильной сессией"""
    from factories import ClientFactory, ParkingFactory

    ClientFactory._meta.sqlalchemy_session = db_session.session
    ParkingFactory._meta.sqlalchemy_session = db_session.session


@pytest.fixture
def client_factory(setup_factories):
    """Фабрика клиентов"""
    from factories import ClientFactory

    return ClientFactory


@pytest.fixture
def parking_factory(setup_factories):
    """Фабрика парковок"""
    from factories import ParkingFactory

    return ParkingFactory


@pytest.fixture
def sample_client_parking(db_session, sample_client, sample_parking):
    """Создание тестового лога парковки"""
    time_in = datetime.now() - timedelta(hours=1)
    client_parking = ClientParking(
        client_id=sample_client.id, parking_id=sample_parking.id, time_in=time_in
    )
    db_session.session.add(client_parking)
    sample_parking.count_available_places -= 1
    db_session.session.commit()
    return client_parking


@pytest.fixture
def client_without_card(db_session):
    """Клиент без привязанной карты"""
    client = Client(
        name="Петр", surname="Петров", credit_card=None, car_number="В456ГД777"
    )
    db_session.session.add(client)
    db_session.session.commit()
    return client


@pytest.fixture
def closed_parking(db_session):
    """Закрытая парковка"""
    parking = Parking(
        address="ул. Закрытая, д. 1",
        opened=False,
        count_places=5,
        count_available_places=5,
    )
    db_session.session.add(parking)
    db_session.session.commit()
    return parking


@pytest.fixture
def full_parking(db_session):
    """Парковка без свободных мест"""
    parking = Parking(
        address="ул. Полная, д. 1",
        opened=True,
        count_places=3,
        count_available_places=0,
    )
    db_session.session.add(parking)
    db_session.session.commit()
    return parking
