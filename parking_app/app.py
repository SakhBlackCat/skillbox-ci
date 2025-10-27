from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///parking.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    from .models import Client, ClientParking, Parking

    # Заменяем before_first_request на контекст приложения
    with app.app_context():
        db.create_all()

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db.session.remove()

    # Роуты для клиентов
    @app.route("/clients", methods=["GET"])
    def get_clients_handler():
        """Получение списка всех клиентов"""
        clients = db.session.query(Client).all()
        clients_list = [client.to_json() for client in clients]
        return jsonify(clients_list), 200

    @app.route("/clients/<int:client_id>", methods=["GET"])
    def get_client_handler(client_id: int):
        """Получение информации о клиенте по ID"""
        client = db.session.get(Client, client_id)
        if not client:
            return jsonify({"error": "Клиент не найден"}), 404
        return jsonify(client.to_json()), 200

    @app.route("/clients", methods=["POST"])
    def create_client_handler():
        """Создание нового клиента"""
        # Получаем данные из JSON или form-data
        if request.is_json:
            data = request.get_json()
            name = data.get("name")
            surname = data.get("surname")
            credit_card = data.get("credit_card")
            car_number = data.get("car_number")
        else:
            name = request.form.get("name", type=str)
            surname = request.form.get("surname", type=str)
            credit_card = request.form.get("credit_card", type=str, default=None)
            car_number = request.form.get("car_number", type=str, default=None)

        if not name or not surname:
            return jsonify({"error": "Имя и фамилия обязательны"}), 400

        new_client = Client(
            name=name, surname=surname, credit_card=credit_card, car_number=car_number
        )

        db.session.add(new_client)
        db.session.commit()

        return jsonify(new_client.to_json()), 201

    # Роуты для парковок
    @app.route("/parkings", methods=["POST"])
    def create_parking_handler():
        """Создание новой парковочной зоны"""
        if request.is_json:
            data = request.get_json()
            address = data.get("address")
            count_places = data.get("count_places")
            opened = data.get("opened", True)
        else:
            address = request.form.get("address", type=str)
            count_places = request.form.get("count_places", type=int)
            opened = request.form.get("opened", type=bool, default=True)

        if not address or not count_places:
            return jsonify({"error": "Адрес и количество мест обязательны"}), 400

        new_parking = Parking(
            address=address,
            opened=opened,
            count_places=count_places,
            count_available_places=count_places,
        )

        db.session.add(new_parking)
        db.session.commit()

        return jsonify(new_parking.to_json()), 201

    # Роуты для работы с парковкой клиентов
    @app.route("/client_parkings", methods=["POST"])
    def enter_parking_handler():
        """Заезд на парковку"""
        if request.is_json:
            data = request.get_json()
            client_id = data.get("client_id")
            parking_id = data.get("parking_id")
        else:
            client_id = request.form.get("client_id", type=int)
            parking_id = request.form.get("parking_id", type=int)

        if not client_id or not parking_id:
            return jsonify({"error": "client_id и parking_id обязательны"}), 400

        # Проверяем существование клиента и парковки
        client = db.session.get(Client, client_id)
        parking = db.session.get(Parking, parking_id)

        if not client:
            return jsonify({"error": "Клиент не найден"}), 404
        if not parking:
            return jsonify({"error": "Парковка не найдена"}), 404

        # Проверяем, открыта ли парковка
        if not parking.opened:
            return jsonify({"error": "Парковка закрыта"}), 400

        # Проверяем наличие свободных мест
        if parking.count_available_places <= 0:
            return jsonify({"error": "Нет свободных мест на парковке"}), 400

        # Проверяем, не находится ли клиент уже на парковке
        active_parking = (
            db.session.query(ClientParking)
            .filter(
                ClientParking.client_id == client_id, ClientParking.time_out.is_(None)
            )
            .first()
        )

        if active_parking:
            return jsonify({"error": "Клиент уже находится на парковке"}), 400

        # Создаем запись о заезде
        from datetime import datetime

        new_client_parking = ClientParking(
            client_id=client_id, parking_id=parking_id, time_in=datetime.now()
        )

        # Уменьшаем количество свободных мест
        parking.count_available_places -= 1

        db.session.add(new_client_parking)
        db.session.commit()

        return (
            jsonify(
                {
                    "message": "Успешный заезд на парковку",
                    "client_parking": new_client_parking.to_json(),
                }
            ),
            201,
        )

    @app.route("/client_parkings", methods=["DELETE"])
    def exit_parking_handler():
        """Выезд с парковки"""
        if request.is_json:
            data = request.get_json()
            client_id = data.get("client_id")
            parking_id = data.get("parking_id")
        else:
            client_id = request.form.get("client_id", type=int)
            parking_id = request.form.get("parking_id", type=int)

        if not client_id or not parking_id:
            return jsonify({"error": "client_id и parking_id обязательны"}), 400

        # Находим активную запись о парковке
        client_parking = (
            db.session.query(ClientParking)
            .filter(
                ClientParking.client_id == client_id,
                ClientParking.parking_id == parking_id,
                ClientParking.time_out.is_(None),
            )
            .first()
        )

        if not client_parking:
            return jsonify({"error": "Активная запись о парковке не найдена"}), 404

        # Проверяем, есть ли у клиента привязанная карта
        client = db.session.get(Client, client_id)
        if not client.credit_card:
            return jsonify({"error": "У клиента не привязана карта для оплаты"}), 400

        # Обновляем запись о парковке
        from datetime import datetime

        client_parking.time_out = datetime.now()

        # Увеличиваем количество свободных мест
        parking = db.session.get(Parking, parking_id)
        parking.count_available_places += 1

        # Рассчитываем время парковки и стоимость (простая логика)
        parking_time = client_parking.time_out - client_parking.time_in
        parking_hours = parking_time.total_seconds() / 3600
        cost = max(1, round(parking_hours * 50))  # 50 рублей в час, минимум 1 рубль

        db.session.commit()

        return (
            jsonify(
                {
                    "message": "Успешный выезд с парковки",
                    "parking_time_hours": round(parking_hours, 2),
                    "cost": cost,
                    "client_parking": client_parking.to_json(),
                }
            ),
            200,
        )

    return app
