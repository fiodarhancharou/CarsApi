from flask import Flask
import requests
from flask_restful import Api, Resource, reqparse, abort, fields, marshal_with
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func


# Download the list of Dealers
makes_url = r'https://vpic.nhtsa.dot.gov/api/vehicles/GetAllMakes?format=csv'
makes = requests.get(makes_url).text
makes = [i.split(',') for i in makes.split('\r')][1:-1]
makes = ([i[1].lower() for i in makes])


app = Flask(__name__)
api = Api(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
db = SQLAlchemy(app)


class CarModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    make = db.Column(db.String(100), nullable=False)
    model = db.Column(db.String(100), nullable=False)
    rate = db.Column(db.Float(32), nullable=False)

    def __repr__(self):
        return f"Car(make = {self.make}, model = {self.model}, rate = {self.rate})"


db.create_all()

car_put_args = reqparse.RequestParser()
car_put_args.add_argument("make", type=str, help="Make of the car", required=True)
car_put_args.add_argument("model", type=str, help="Model of the car", required=True)
car_put_args.add_argument("rate", type=float, help="Rating of the car", default=1.0)

car_update_args = reqparse.RequestParser()
car_update_args.add_argument("car_id", type=int, help="id of the car", required=True)
car_update_args.add_argument("rating", type=float, help="Rating of the car in the range [1,5]", required=True)

resource_fields_get = {
    'id': fields.String,
    'make': fields.String,
    'model': fields.String,
    'avg_rating': fields.Float
}


@api.resource("/cars", "/cars/")
class Cars(Resource):
    def post(self):
        args = car_put_args.parse_args()
        make = args['make'].lower()
        if make not in makes:
            abort(404, message="Make doesn't exist")
        models_url = f'https://vpic.nhtsa.dot.gov/api/vehicles/GetModelsForMake/{make}?format=csv'
        models = requests.get(models_url).text
        models = [i.split(',') for i in models.split('\r')][1:-1]
        models = ([i[3].lower() for i in models])
        model = args['model'].lower()
        if model not in models:
            abort(404, message="Model doesn't exist")
        car = CarModel(make=make.capitalize(), model=model.capitalize(), rate=args['rate'])
        db.session.add(car)
        db.session.commit()
        return 201

    @marshal_with(resource_fields_get)
    def get(self):
        query = db.session.query(CarModel.id, CarModel.make, CarModel.model,func.avg(CarModel.rate))\
                .group_by(CarModel.make, CarModel.model) \
                .order_by(CarModel.id.asc())
        result = db.session.execute(query).fetchall()
        res_list = []
        for i in result:
            res_list.append({'id': i[0], 'make': i[1], 'model': i[2], 'avg_rating': round(i[3], 1)})
        if not result:
            abort(404, message='The database is empty')
        return res_list, 200


@api.resource("/rate", "/rate/")
class CarsRating(Resource):
    def post(self):
        args = car_update_args.parse_args()
        result = CarModel.query.filter_by(id=args['car_id']).first()
        if not result:
            abort(404, message="Car doesn't exist, cannot update")
        if 1 <= args['rating'] <= 5:
            result.rate = args['rating']
        else:
            abort(404, message="Value does not satisfy the range [1,5]")
        db.session.commit()
        return 201


@api.resource("/cars/<int:car_id>")
class DeleteCar(Resource):
    def delete(self, car_id):
        result = CarModel.query.filter_by(id=car_id).first()
        if not result:
            abort(404, message="Could not find the car...")
        db.session.delete(result)
        db.session.commit()
        return 204


@api.resource("/popular", "/popular/")
class PopularCars(Resource):
    @marshal_with({'make': fields.String, 'model': fields.String, 'rates_number': fields.Integer})
    def get(self):
        query = db.session.query(CarModel.id, CarModel.make, CarModel.model, func.count(CarModel.rate)) \
            .group_by(CarModel.make, CarModel.model)\
            .order_by(func.count(CarModel.rate).desc())
        result = db.session.execute(query).fetchall()
        res_list = []
        for i in result:
            res_list.append({'id': i[0], 'make': i[1], 'model': i[2], 'rates_number': i[3]})
        if not result:
            abort(404, message=f'The database is empty')
        return res_list, 200