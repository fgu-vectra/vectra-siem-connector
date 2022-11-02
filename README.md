## Vectra SaaS to Sentinel

Pull events from Vectra SaaS to make them available in Sentinel


## Installation

```
git clone 
```

## Configuration

Edit config.py to add:

- URL of Vectra SaaS
- Client ID
- Client secret


## Build docker

``` 
sudo docker build . -t vectra_saas
sudo docker run -it --rm -v $(pwd)/connector/:/app/connector/ vectra_saas
```