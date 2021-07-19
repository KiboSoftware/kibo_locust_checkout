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
    "app_id": "??????",
    "app_secrete": "??????",
    
}
```
### run

* dev
```bash
locust --config confs/dev.conf
```

### senarios / conf files
* ./confs/dev.conf : sandbox lite load
* ./confs/perf_sample.conf : perf data set with 1 user
* ./confs/perf_full.conf : perf data set with load to generate 120k carts/ 60 submitted orders and hour.
