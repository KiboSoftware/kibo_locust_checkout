from locust import HttpUser, task, between, tag
from locust import events
import random
import copy
import re
import json
import uuid
import csv
from datetime import datetime, timedelta
import logging


logger = logging.getLogger(__name__)


class Checkout(HttpUser):
    wait_time = between(.3, 5)

    @events.init.add_listener
    def on_locust_init(environment, **kwargs):
        environment.token_exp = datetime.now()
        host = re.search(r".*\/\/([^\/:]+)", environment.host)[1].lower()

        with open('datafiles/{}/env.json'.format(host), 'r') as f:
            environment.env = json.load(f)
        environment.products = []
        with open('datafiles/{}/products.csv'.format(host), 'r') as csvfile:
            csvreader = csv.reader(csvfile)
            # if header
            # fields = next(csvreader)
            for row in csvreader:
                environment.products.append(row)
        environment.users = []
        with open('datafiles/{}/users.csv'.format(host), 'r') as csvfile:
            csvreader = csv.reader(csvfile)
            # if header
            # fields = next(csvreader)
            for row in csvreader:
                environment.users.append(row)

    def get_token(self):
        if datetime.now() >= self.environment.token_exp:
            self.client.headers = {}
            resp = self.client.post(
                '{}/api/platform/applications/authtickets/oauth'.format(
                    self.environment.env['auth_server']),
                data={
                    "client_id": str(self.environment.env["app_id"]),
                    "client_secret": str(self.environment.env["app_secrete"]),
                    "grant_type": "client"
                },
                name='oauth')
            self.environment.token = resp.json()
            self.environment.token_exp = datetime.now(
            ) + timedelta(seconds=self.environment.token["expires_in"])
        return self.environment.token['access_token']

    def get_or_create_cart(self, user_id):
        resp = self.client.post(
            '/api/commerce/carts/user/{}?responseFields=id'.format(user_id),
            name='get_or_create_cart'
        )
        self.log_on_non_success(resp)
        return resp.json()['id']

    def log_on_non_success(self, resp):
        if (resp.status_code > 400):
            msg = resp.json()
            logger.warning(msg)
            return False
        return True

    def add_product_to_cart(self, product, cart_id):
        body = {
            "product": {
                "productCode": product[0],
                "variationProductCode": product[1],
                "options": [
                    {
                        "attributeFQN": product[2],
                        "value": product[3],
                    }]
            },
            "quantity": 1,
            "fulfillmentMethod": "Ship"
        }
        resp = self.client.post(
            '/api/commerce/carts/{}/items?responseFields=id'.format(
                cart_id),
            json=body,
            name='add_item_to_cart'
        )
        return self.log_on_non_success(resp)

    def create_order_from_cart(self, cart_id):
        resp = self.client.post(
            '/api/commerce/orders?cartId={}&responseFields=id'.format(
                cart_id),
            name='create_order_from_cart'
        )
        self.log_on_non_success(resp)

        order_id = resp.json()['id']
        return order_id

    def set_fulfillment(self, order_id, user):
        address = random.choice(self.environment.env["addresses"])
        body = {
            "fulfillmentContact": {
                "address": address,
                "orderId": order_id,
                "firstName": "test",
                "lastNameOrSurname": "user",
                "email": user[1],
                "phoneNumbers": {
                    "home": "5555551212"
                }
            },
            "shippingMethodCode": "flat"
        }

        resp = self.client.put(
            '/api/commerce/orders/{}/fulfillmentinfo?responseFields=id'.format(
                order_id),
            json=body,
            name='set_fulfillment_info')
        self.log_on_non_success(resp)

    def set_payment(self, order_id, user):
        body = {
            "currencyCode": "USD",
            "newBillingInfo": {
                "check": {
                    "nameOnCheck": "bing bong",
                    "routingNumber": "123",
                    "checkNumber": "123"
                },
                "card": {
                    "isSavedCard": False
                },
                "paymentWorkflow": "Mozu",
                "usingSavedCard": False,
                "paymentType": "Check",
                "isSameBillingShippingAddress": True
            }
        }

        resp = self.client.post(
            '/api/commerce/orders/{}/payments/actions?responseFields=id'.format(
                order_id),
            json=body,
            name='set_payment_info')
        self.log_on_non_success(resp)

    def create_customer(self, order_id, user):
        body = {
            "emailAddress": user[1],
            "userName": user[1],
            "firstName": user[1].split('.')[0],
            "lastName": user[1].split('.')[-1],
            "userId": user[0],
            "isActive": True,
            "accountType": "B2C"
        }
        resp = self.client.post(
            '/api/commerce/customer/accounts?responseFields=id',
            json=body,
            name='create_user')
        self.log_on_non_success(resp)
        return resp.json()['id']

    def add_customer_to_order(self, order_id, customer_id):
        body = self.client.get('/api/commerce/orders/{}?responseFields=fulfillmentInfo,email,userId'.format(
            order_id),
            name='get_order').json()
        body['customerAccountId'] = customer_id

        resp = self.client.put(
            '/api/commerce/orders/{}?responseFields=id'.format(
                order_id),
            json=body,
            name='update_order')
        self.log_on_non_success(resp)
        return resp.json()['id']

    def submit_order(self, order_id, user):
        body = {
            "actionName": "SubmitOrder"
        }
        resp = self.client.post(
            '/api/commerce/orders/{}/actions?responseFields=id'.format(
                order_id),
            json=body,
            name='submit_order')
        self.log_on_non_success(resp)

    # @tag('auth_user')
    # @task(5)
    # def auth_user(self):
    #     token = self.get_token()
    #     self.client.headers.update(
    #         {'Authorization': 'Bearer {}'.format(token)})
    #     user = random.choice(
    #         self.environment.users)
    #     cart_id = self.get_or_create_cart(user[0])
    #     for x in range(0, 5):
    #         product = random.choice(
    #             self.environment.products)
    #         self.add_product_to_cart(product, cart_id)
    #     order_id = self.create_order_from_cart(cart_id)
    #     self.set_fulfillment(order_id, user)
    #     self.set_payment(order_id, user)
    #     self.submit_order(order_id, user)

    @ tag('anon_user')
    @ task(5)
    def anaon_user(self):
        token = self.get_token()
        self.client.headers.update(
            {'Authorization': 'Bearer {}'.format(token)})
        user_id = str(uuid.uuid4()).replace('-', '')
        user_email = 'test.user{}@test.com'.format(
            random.randrange(1, 1000000000, 1))
        user = [user_id, user_email]
        cart_id = self.get_or_create_cart(user[0])
        for x in range(0, 5):
            product = random.choice(
                self.environment.products)
            self.add_product_to_cart(product, cart_id)
        order_id = self.create_order_from_cart(cart_id)
        self.set_fulfillment(order_id, user)
        self.set_payment(order_id, user)
        customer_id = self.create_customer(order_id, user)
        self.add_customer_to_order(order_id, customer_id)
        self.submit_order(order_id, user)
