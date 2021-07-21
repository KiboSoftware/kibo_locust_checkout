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

proxies = {
    # "http": "http://localhost:8866",
    # "https": "http://localhost:8866"
}
logger = logging.getLogger(__name__)


class Checkout2(HttpUser):
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
            '/api/commerce/carts/user/{}?responseFields=id,items(id)'.format(
                user_id),
            name='get_or_create_cart'
        )
        self.log_on_non_success(resp)
        cart = resp.json()
        if cart.get('items') and len(cart.get('items')) > 1:
            resp = self.client.delete(
                '/api/commerce/carts/{}/items?responseFields=id'.format(
                    cart['id']),
                name='clear_cart'
            )
        self.log_on_non_success(resp)

        return cart['id']

    def log_on_non_success(self, resp):
        if (resp.status_code > 399):
            if resp.headers.get('content-type') and resp.headers.get('content-type').lower().find("json") > 1:
                msg = resp.json()
            else:
                msg = resp.text
            logger.warning(msg)
            return False
        return True

    def add_product_to_cart(self, product, cart_id):

        resp = self.client.post(
            '/api/commerce/carts/{}/items?responseFields=id'.format(
                cart_id),
            json=product,
            name='add_item_to_cart'
        )
        return self.log_on_non_success(resp)

    def add_products_to_cart(self, products, cart_id):
        resp = self.client.post(
            '/api/commerce/carts/{}/bulkitems?responseFields=id,item(id)'.format(
                cart_id),
            json=products,
            name='add_items_to_cart'
        )
        return self.log_on_non_success(resp)

    def create_order_from_cart(self, cart_id):
        resp = self.client.post(
            '/api/commerce/orders?cartId={}&responseFields=id'.format(
                cart_id),
            name='create_order_from_cart'
        )
        if not self.log_on_non_success(resp):
            resp = self.client.delete(
                '/api/commerce/carts/{}/items?responseFields=id'.format(
                    cart_id),
                name='clear_cart'
            )

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
            'https://t29621-s48972.tp1.kibong-perf.com/api/commerce/customer/accounts?responseFields=id',
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

    def random_pricelist(self, user):
        pl_num = 1 + (int(user[2]) % self.environment.env["priceListCount"])
        return 'pricelist_{}'.format(pl_num)

    def random_user(self, anon):
        if (anon):
            user_id = str(uuid.uuid4()).replace('-', '')
            user_num = random.randrange(1, 1000000000, 1)
            user_email = 'test.user{}@test.com'.format(user_num)
            return [user_id, user_email, user_num]
        return random.choice(self.environment.users)

    def random_product(self, bogo=False):
        if bogo:
            prod_id = random.randrange(
                1, self.environment.env["bogoCount"])
        else:
            prod_id = random.randrange(
                1, self.environment.env["productCount"])
        product = 'prod_{}'.format(prod_id)
        color = random.choice(self.environment.env["colors"])
        size = random.choice(self.environment.env["sizes"])
        sku = '{}_{}_{}'.format(product, color, size)
        return {
            "product": {
                "productCode": product,
                "variationProductCode": sku,
                "options": [
                    {
                        "attributeFQN": "tenant~color",
                        "value": color,
                    },
                    {
                        "attributeFQN": "tenant~size",
                        "value": size,
                    }]
            },
            "quantity": 1,
            "fulfillmentMethod": "Ship"
        }

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

    def init_haders(self, token, pricelist):
        self.client.proxies = proxies
        if proxies.get("https"):
            self.client.verify = False
        self.client.base_url = re.search(
            r"http.*\/\/[^\/]*", self.environment.host)[0]
        self.client.headers.update(
            {
                'Authorization': 'Bearer {}'.format(token),
                'x-vol-pricelist': pricelist
            })
        self.client.headers.update(
            {'x-vol-locale': 'en-US',
             'x-vol-currency': 'USD',
             'x-vol-tenant': '29621',
             'x-vol-site': '48972',
             'x-vol-master-catalog': '1',
             'x-vol-catalog': '1'})

    def add_products(self, cart_id):
        products = [self.random_product(True),
                    self.random_product(),
                    self.random_product()]
        self.add_products_to_cart(products, cart_id)
        self.add_product_to_cart(self.random_product(), cart_id)

    @ tag('auth_user')
    @ task(5)
    def auth_user(self):
        token = self.get_token()
        user = self.random_user(False)
        pricelist = self.random_pricelist(user)
        self.init_haders(token, pricelist)
        cart_id = self.get_or_create_cart(user[0])

        self.add_products(cart_id)
        order_id = self.create_order_from_cart(cart_id)
        self.set_fulfillment(order_id, user)
        self.set_payment(order_id, user)
        self.submit_order(order_id, user)

    @ tag('anon_user')
    @ task(5)
    def anaon_user(self):
        token = self.get_token()
        user = self.random_user(True)
        pricelist = self.random_pricelist(user)
        self.init_haders(token, pricelist)
        user_id = str(uuid.uuid4()).replace('-', '')
        user_email = 'test.user{}@test.com'.format(
            random.randrange(1, 1000000000, 1))
        user = [user_id, user_email]
        cart_id = self.get_or_create_cart(user[0])
        self.add_products(cart_id)
        order_id = self.create_order_from_cart(cart_id)
        self.set_fulfillment(order_id, user)
        self.set_payment(order_id, user)
        customer_id = self.create_customer(order_id, user)
        self.add_customer_to_order(order_id, customer_id)
        self.submit_order(order_id, user)

    @ tag('anon_user_abandon')
    @ task(10)
    def anon_user_abandon(self):
        token = self.get_token()
        user = self.random_user(True)
        pricelist = self.random_pricelist(user)
        self.init_haders(token, pricelist)
        user_id = str(uuid.uuid4()).replace('-', '')
        user_email = 'test.user{}@test.com'.format(
            random.randrange(1, 1000000000, 1))
        user = [user_id, user_email]
        cart_id = self.get_or_create_cart(user[0])
        self.add_products(cart_id)
