## Sample Locust test script for Kibo Cart / Checkout


* install python dependencies 
```bash
pip3 install -r requirements.txt
```


* update the conf to point to you env
```
locustfile = locustfiles/checkout.py
host =  https://[host]
```

* author or copy the datafiles to datafiles/[host] 

* update the datafiles/[host]/env.json 
```json
{
    "auth_server": "https://home.mozu.com",
    "app_id": "??????",
    "app_secrete": "??????",
    
}
```
### run

* dev
```bash
locust --config confs/dev.conf
```