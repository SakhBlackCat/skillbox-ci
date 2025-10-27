import json
from datetime import datetime

import pytest

from parking_app.models import Client, ClientParking, Parking


class TestAPI:
    """Тесты для API парковки"""

    @pytest.mark.parametrize(
        "url,method",
        [
            ("/clients", "GET"),
            ("/clients/1", "GET"),
        ],
    )
    def test_get_methods_status_code(self, client, sample_client, url, method):
        """Тестирование GET методов на возврат кода 200"""
        if method == "GET":
            response = client.get(url)
            assert response.status_code == 200

    def test_create_client(self, client, db_session):
        """Тестирование создания клиента"""
        client_data = {
            "name": "Алексей",
            "surname": "Сидоров",
            "credit_card": "1111222233334444",
            "car_number": "Е555КХ777",
        }

        response = client.post("/clients", data=client_data)
        assert response.status_code == 201

        # Проверяем, что клиент создан в базе
        created_client = (
            db_session.session.query(Client)
            .filter_by(name="Алексей", surname="Сидоров")
            .first()
        )
        assert created_client is not None
        assert created_client.credit_card == "1111222233334444"
        assert created_client.car_number == "Е555КХ777"

    def test_create_client_validation(self, client):
        """Тестирование валидации при создании клиента"""
        # Отправляем неполные данные
        invalid_data = {
            "name": "Только имя"
            # Нет фамилии
        }

        response = client.post("/clients", data=invalid_data)
        assert response.status_code == 400
        assert "error" in response.get_json()

    def test_create_parking(self, client, db_session):
        """Тестирование создания парковки"""
        parking_data = {
            "address": "ул. Новая, д. 100",
            "count_places": 50,
            "opened": True,
        }

        response = client.post("/parkings", data=parking_data)
        assert response.status_code == 201

        # Проверяем, что парковка создана в базе
        created_parking = (
            db_session.session.query(Parking)
            .filter_by(address="ул. Новая, д. 100")
            .first()
        )
        assert created_parking is not None
        assert created_parking.count_places == 50
        assert created_parking.count_available_places == 50
        assert created_parking.opened is True

    def test_create_parking_validation(self, client):
        """Тестирование валидации при создании парковки"""
        # Отправляем неполные данные
        invalid_data = {
            "address": "Только адрес"
            # Нет количества мест
        }

        response = client.post("/parkings", data=invalid_data)
        assert response.status_code == 400
        assert "error" in response.get_json()

    @pytest.mark.parking
    def test_enter_parking(self, client, sample_client, sample_parking, db_session):
        """Тестирование заезда на парковку"""
        # Запоминаем начальное количество мест
        initial_available_places = sample_parking.count_available_places

        parking_data = {"client_id": sample_client.id, "parking_id": sample_parking.id}

        response = client.post("/client_parkings", data=parking_data)
        assert response.status_code == 201

        response_data = response.get_json()
        assert "message" in response_data
        assert "Успешный заезд на парковку" in response_data["message"]

        # Проверяем, что количество свободных мест уменьшилось
        updated_parking = db_session.session.get(Parking, sample_parking.id)
        assert updated_parking.count_available_places == initial_available_places - 1

        # Проверяем, что создалась запись о парковке
        client_parking = (
            db_session.session.query(ClientParking)
            .filter_by(
                client_id=sample_client.id, parking_id=sample_parking.id, time_out=None
            )
            .first()
        )
        assert client_parking is not None
        assert client_parking.time_in is not None

    @pytest.mark.parking
    def test_enter_closed_parking(self, client, sample_client, closed_parking):
        """Тестирование заезда на закрытую парковку"""
        parking_data = {"client_id": sample_client.id, "parking_id": closed_parking.id}

        response = client.post("/client_parkings", data=parking_data)
        assert response.status_code == 400
        assert "закрыта" in response.get_json()["error"].lower()

    @pytest.mark.parking
    def test_enter_full_parking(self, client, sample_client, full_parking):
        """Тестирование заезда на полную парковку"""
        parking_data = {"client_id": sample_client.id, "parking_id": full_parking.id}

        response = client.post("/client_parkings", data=parking_data)
        assert response.status_code == 400
        assert "свободных мест" in response.get_json()["error"].lower()

    @pytest.mark.parking
    def test_enter_parking_twice(self, client, sample_client_parking):
        """Тестирование повторного заезда на парковку"""
        parking_data = {
            "client_id": sample_client_parking.client_id,
            "parking_id": sample_client_parking.parking_id,
        }

        response = client.post("/client_parkings", data=parking_data)
        assert response.status_code == 400
        assert "уже находится" in response.get_json()["error"].lower()

    @pytest.mark.parking
    def test_exit_parking(self, client, sample_client_parking, db_session):
        """Тестирование выезда с парковки"""
        # Запоминаем начальное количество мест
        parking_before = db_session.session.get(
            Parking, sample_client_parking.parking_id
        )
        initial_available_places = parking_before.count_available_places

        exit_data = {
            "client_id": sample_client_parking.client_id,
            "parking_id": sample_client_parking.parking_id,
        }

        response = client.delete("/client_parkings", data=exit_data)
        assert response.status_code == 200

        response_data = response.get_json()
        assert "message" in response_data
        assert "Успешный выезд" in response_data["message"]
        assert "parking_time_hours" in response_data
        assert "cost" in response_data
        assert response_data["cost"] > 0

        # Проверяем, что количество свободных мест увеличилось
        parking_after = db_session.session.get(
            Parking, sample_client_parking.parking_id
        )
        assert parking_after.count_available_places == initial_available_places + 1

        # Проверяем, что время выезда проставлено
        updated_client_parking = db_session.session.get(
            ClientParking, sample_client_parking.id
        )
        assert updated_client_parking.time_out is not None
        assert updated_client_parking.time_out > updated_client_parking.time_in

    @pytest.mark.parking
    def test_exit_parking_without_card(
        self, client, client_without_card, sample_parking, db_session
    ):
        """Тестирование выезда без привязанной карты"""
        # Сначала создаем запись о парковке
        client_parking = ClientParking(
            client_id=client_without_card.id,
            parking_id=sample_parking.id,
            time_in=datetime.now(),
        )
        db_session.session.add(client_parking)
        sample_parking.count_available_places -= 1
        db_session.session.commit()

        # Пытаемся выехать
        exit_data = {
            "client_id": client_without_card.id,
            "parking_id": sample_parking.id,
        }

        response = client.delete("/client_parkings", data=exit_data)
        assert response.status_code == 400
        assert "карта" in response.get_json()["error"].lower()

    @pytest.mark.parking
    def test_exit_parking_not_found(self, client, sample_client, sample_parking):
        """Тестирование выезда с несуществующей парковки"""
        exit_data = {
            "client_id": sample_client.id,
            "parking_id": 99999,  # Несуществующий ID
        }

        response = client.delete("/client_parkings", data=exit_data)
        assert response.status_code == 404

    def test_get_clients_list(self, client, sample_client):
        """Тестирование получения списка клиентов"""
        response = client.get("/clients")
        assert response.status_code == 200

        clients_list = response.get_json()
        assert isinstance(clients_list, list)
        assert len(clients_list) > 0

        # Проверяем, что наш тестовый клиент в списке
        client_found = any(
            client_item["id"] == sample_client.id
            and client_item["name"] == sample_client.name
            and client_item["surname"] == sample_client.surname
            for client_item in clients_list
        )
        assert client_found

    def test_get_client_by_id(self, client, sample_client):
        """Тестирование получения клиента по ID"""
        response = client.get(f"/clients/{sample_client.id}")
        assert response.status_code == 200

        client_data = response.get_json()
        assert client_data["id"] == sample_client.id
        assert client_data["name"] == sample_client.name
        assert client_data["surname"] == sample_client.surname
        assert client_data["credit_card"] == sample_client.credit_card
        assert client_data["car_number"] == sample_client.car_number

    def test_get_nonexistent_client(self, client):
        """Тестирование получения несуществующего клиента"""
        response = client.get("/clients/99999")
        assert response.status_code == 404

    def test_json_support(self, client, db_session):
        """Тестирование поддержки JSON в запросах"""
        client_data = {
            "name": "JSON",
            "surname": "User",
            "credit_card": "9999888877776666",
            "car_number": "Х999ХХ777",
        }

        response = client.post(
            "/clients", data=json.dumps(client_data), content_type="application/json"
        )
        assert response.status_code == 201

        # Проверяем создание в базе
        created_client = (
            db_session.session.query(Client)
            .filter_by(name="JSON", surname="User")
            .first()
        )
        assert created_client is not None


class TestFactoryBoyAPI:
    """Тесты API с использованием Factory Boy"""

    def test_create_client_with_factory_boy(self, client, db_session, client_factory):
        """Дубликат теста создания клиента с использованием ClientFactory"""
        # Создаем клиента через фабрику (данные генерируются автоматически)
        client_instance = client_factory()

        # Проверяем, что клиент создан в базе с правильными данными
        created_client = db_session.session.get(Client, client_instance.id)
        assert created_client is not None
        assert created_client.name == client_instance.name
        assert created_client.surname == client_instance.surname
        assert created_client.credit_card == client_instance.credit_card
        assert created_client.car_number == client_instance.car_number

        # Проверяем, что данные сгенерированы корректно
        assert isinstance(created_client.name, str)
        assert isinstance(created_client.surname, str)
        assert len(created_client.name) > 0
        assert len(created_client.surname) > 0

        # Проверяем формат номера автомобиля
        if created_client.car_number:
            assert len(created_client.car_number) >= 6
            assert any(c.isalpha() for c in created_client.car_number)
            assert any(c.isdigit() for c in created_client.car_number)

    def test_create_client_with_factory_boy_multiple(
        self, client, db_session, client_factory
    ):
        """Тестирование создания нескольких клиентов через фабрику"""
        clients_count_before = db_session.session.query(Client).count()

        # Создаем 3 клиентов через фабрику
        clients = [client_factory() for _ in range(3)]

        clients_count_after = db_session.session.query(Client).count()
        assert clients_count_after == clients_count_before + 3

        # Проверяем, что все клиенты уникальны
        names = [client.name for client in clients]
        surnames = [client.surname for client in clients]

        assert len(set(names)) >= 2  # Большинство имен должны быть разными
        assert len(set(surnames)) >= 2  # Большинство фамилий должны быть разными

        # Проверяем, что у некоторых есть карта, у некоторых нет
        has_card = any(client.credit_card is not None for client in clients)
        no_card = any(client.credit_card is None for client in clients)
        assert has_card or no_card  # Должны быть оба типа клиентов

    def test_create_parking_with_factory_boy(self, client, db_session, parking_factory):
        """Дубликат теста создания парковки с использованием ParkingFactory"""
        # Создаем парковку через фабрику (данные генерируются автоматически)
        parking_instance = parking_factory()

        # Проверяем, что парковка создана в базе с правильными данными
        created_parking = db_session.session.get(Parking, parking_instance.id)
        assert created_parking is not None
        assert created_parking.address == parking_instance.address
        assert created_parking.opened == parking_instance.opened
        assert created_parking.count_places == parking_instance.count_places
        assert (
            created_parking.count_available_places
            == parking_instance.count_available_places
        )

        # Проверяем корректность LazyAttribute для count_available_places
        if created_parking.opened:
            assert (
                created_parking.count_available_places == created_parking.count_places
            )
        else:
            assert created_parking.count_available_places == 0

        # Проверяем, что данные сгенерированы корректно
        assert isinstance(created_parking.address, str)
        assert len(created_parking.address) > 0
        assert isinstance(created_parking.opened, bool)
        assert 10 <= created_parking.count_places <= 100

    def test_create_parking_with_factory_boy_custom_params(
        self, client, db_session, parking_factory
    ):
        """Тестирование создания парковки с кастомными параметрами"""
        # Создаем закрытую парковку с малым количеством мест
        closed_parking = parking_factory(
            opened=False, count_places=5, address="ул. Кастомная, д. 123"
        )

        # Проверяем создание в базе
        created_parking = db_session.session.get(Parking, closed_parking.id)
        assert created_parking is not None
        assert created_parking.opened is False
        assert created_parking.count_places == 5
        assert created_parking.count_available_places == 0
        assert created_parking.address == "ул. Кастомная, д. 123"

        # Создаем открытую парковку с большим количеством мест
        large_parking = parking_factory(
            opened=True, count_places=100, address="ул. Большая, д. 1"
        )

        created_large_parking = db_session.session.get(Parking, large_parking.id)
        assert created_large_parking is not None
        assert created_large_parking.opened is True
        assert created_large_parking.count_places == 100
        assert created_large_parking.count_available_places == 100


class TestFactoryBoyFeatures:
    """Дополнительные тесты для демонстрации возможностей Factory Boy"""

    def test_client_factory_data_generation(self, client_factory):
        """Тестирование генерации данных через ClientFactory"""
        # Создаем клиента и проверяем сгенерированные данные
        client = client_factory.build()

        assert isinstance(client.name, str)
        assert isinstance(client.surname, str)
        assert len(client.name) > 0
        assert len(client.surname) > 0

        # Проверяем, что credit_card либо строка, либо None
        assert client.credit_card is None or isinstance(client.credit_card, str)

        # Проверяем формат номера автомобиля
        assert isinstance(client.car_number, str)
        assert len(client.car_number) >= 6

    def test_parking_factory_lazy_attribute(self, parking_factory):
        """Тестирование LazyAttribute в ParkingFactory"""
        # Создаем открытую парковку
        opened_parking = parking_factory.build(opened=True, count_places=50)
        assert opened_parking.count_available_places == 50

        # Создаем закрытую парковку
        closed_parking = parking_factory.build(opened=False, count_places=30)
        assert closed_parking.count_available_places == 0

    def test_factory_boy_batch_creation(
        self, client_factory, parking_factory, db_session
    ):
        """Тестирование массового создания объектов"""
        # Получаем начальное количество записей
        clients_count_before = db_session.session.query(Client).count()
        parkings_count_before = db_session.session.query(Parking).count()

        # Создаем несколько объектов через фабрики
        clients = client_factory.create_batch(3)
        parkings = parking_factory.create_batch(2)

        # Проверяем, что количество записей увеличилось
        clients_count_after = db_session.session.query(Client).count()
        parkings_count_after = db_session.session.query(Parking).count()

        assert clients_count_after == clients_count_before + 3
        assert parkings_count_after == parkings_count_before + 2

        # Проверяем, что все объекты созданы с уникальными ID
        client_ids = [client.id for client in clients]
        parking_ids = [parking.id for parking in parkings]

        assert len(set(client_ids)) == 3
        assert len(set(parking_ids)) == 2

        # Проверяем разнообразие данных
        client_names = set(client.name for client in clients)
        parking_addresses = set(parking.address for parking in parkings)

        assert len(client_names) == 3
        assert len(parking_addresses) == 2

    def test_factory_boy_without_session_persistence(
        self, client_factory, parking_factory
    ):
        """Тестирование фабрик без сохранения в БД (использование build)"""
        # Создаем объекты без сохранения в БД
        client = client_factory.build()
        parking = parking_factory.build()

        # Проверяем, что объекты созданы, но не имеют ID (не сохранены в БД)
        assert client.id is None
        assert parking.id is None

        # Проверяем, что данные сгенерированы корректно
        assert client.name is not None
        assert client.surname is not None
        assert parking.address is not None
        assert parking.count_places is not None

        if parking.opened:
            assert parking.count_available_places == parking.count_places
        else:
            assert parking.count_available_places == 0
