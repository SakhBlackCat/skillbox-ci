import factory
from factory.alchemy import SQLAlchemyModelFactory
from faker import Faker

from parking_app.app import db
from parking_app.models import Client, Parking

fake = Faker("ru_RU")


class ClientFactory(SQLAlchemyModelFactory):
    """Фабрика для создания клиентов"""

    class Meta:
        model = Client
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "commit"

    name = factory.LazyFunction(lambda: fake.first_name())
    surname = factory.LazyFunction(lambda: fake.last_name())
    credit_card = factory.LazyAttribute(
        lambda o: (
            fake.credit_card_number()
            if fake.boolean(chance_of_getting_true=80)
            else None
        )
    )
    car_number = factory.LazyFunction(
        lambda: f"{fake.random_uppercase_letter()}{fake.random_number(digits=3)}{fake.random_uppercase_letter()}{fake.random_uppercase_letter()}{fake.random_number(digits=3)}"
    )


class ParkingFactory(SQLAlchemyModelFactory):
    """Фабрика для создания парковок"""

    class Meta:
        model = Parking
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "commit"

    address = factory.LazyFunction(lambda: fake.address())
    opened = factory.LazyFunction(lambda: fake.boolean(chance_of_getting_true=90))
    count_places = factory.LazyFunction(lambda: fake.random_int(min=10, max=100))
    count_available_places = factory.LazyAttribute(
        lambda o: o.count_places if o.opened else 0
    )
