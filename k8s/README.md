# Pokretanje sistema na Kubernetes-u

## 1. Build Docker image-a

Ako koristiš **minikube**:

```bash
eval $(minikube docker-env)
```

Ako koristiš **kind**, prvo build-uješ pa `kind load docker-image`.

Zatim iz root foldera projekta:

```bash
docker build -t auth-service:latest ./auth_service
docker build -t director-service:latest ./director-service
docker build -t employee-service:latest ./employee-service
```

(Ako koristiš kind: `kind load docker-image auth-service:latest director-service:latest employee-service:latest`)

## 2. Primena YAML fajlova

Redosled nije striktno bitan (init container-i čekaju baze), ali logično je ovako:

```bash
kubectl apply -f ./secret.yaml
kubectl apply -f ./configmap.yaml

kubectl apply -f ./auth-db.yaml
kubectl apply -f ./mongo-db.yaml
kubectl apply -f ./redis.yaml
kubectl apply -f ./blockchain.yaml

kubectl apply -f ./auth-service.yaml
kubectl apply -f ./director-service.yaml
kubectl apply -f ./employee-service.yaml
```

Ili sve odjednom: `kubectl apply -f k8s/`

## 3. Provera

```bash
kubectl get pods
kubectl get svc
```

`employee-service` treba da ima 3/3 spremna pod-a.

Da bi pristupio servisima spolja (npr. iz Postman-a), najlakše je port-forward:

```bash
kubectl port-forward svc/auth-service 5001:5001
kubectl port-forward svc/employee-service 5002:5002
kubectl port-forward svc/director-service 5003:5003
```

## Napomene / pretpostavke koje sam napravio

- **Nazivi image-a**: pretpostavio sam lokalni build (`auth-service:latest` itd.) sa
  `imagePullPolicy: IfNotPresent`, uobičajeno za minikube/kind. Ako pushuješ na neki
  registry (Docker Hub, GHCR...), promeni `image:` polje u odgovarajućim Deployment-ima
  i postavi `imagePullPolicy: Always` (ili ostavi IfNotPresent ako je tag jedinstven).
- Izmenio sam `app.py` u sva tri servisa da čitaju konfiguraciju (host baze, port, JWT
  ključ...) iz environment varijabli umesto da su hardkodovane na `localhost` - to je
  neophodno da bi ConfigMap/Secret uopšte imali efekta.
- `auth-service` ima **initContainer** koji poziva `init_db.py` (kreira tabele + upisuje
  početnog direktora Scrooge McDuck). Proverava da li direktor već postoji, pa je bezbedno
  da se izvrši više puta (npr. ako se pod restartuje).
- `auth-db` i `mongo-db` imaju **PVC** (PersistentVolumeClaim) da podaci prežive restart
  pod-a - to spec eksplicitno traži ("trajno čuvanje podataka").
- `redis-service` i `blockchain` **nemaju** PVC jer čuvaju samo privremene podatke.
- `employee-service` ima `replicas: 3`, kako spec traži.
- Svi Dockerfile-ovi i `requirements.txt` za `director-service`/`employee-service` nisu
  postojali u projektu pa sam ih dodao - proveri da li odgovaraju verzijama biblioteka
  koje koristiš lokalno.
