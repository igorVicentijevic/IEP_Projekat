# Pokretanje sistema na Kubernetes-u

## 1. Pokretanje Docker Desktop Kubernetes-a

U Docker Desktop-u omogući **Settings > Kubernetes > Enable Kubernetes** i
sačekaj da Kubernetes status postane `Running`. Zatim proveri da je klaster dostupan:

```bash
kubectl get nodes
```

## 2. Build Docker image-a

Iz root foldera projekta:

```bash
docker build -t auth-service:latest ./auth_service
docker build -t director-service:latest ./director-service
docker build -t employee-service:latest ./employee-service
```

Docker Desktop Kubernetes koristi lokalno Docker Desktop image skladište, pa dodatno
učitavanje slika u klaster nije potrebno.

## 3. Primena YAML fajlova

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

## 4. Provera

```bash
kubectl get pods
kubectl get svc
```

`employee-service` treba da ima 3/3 spremna pod-a.

## Korisne Kubernetes komande

Docker Desktop uključuje `kubectl.exe`, koji se koristi za upravljanje lokalnim
Kubernetes klasterom.

| Komanda | Namena |
| --- | --- |
| `kubectl.exe apply -f <ime-fajla>` | Primena YAML manifesta, na primer Deployment-a. |
| `kubectl.exe get deployment` | Prikaz svih Deployment resursa. |
| `kubectl.exe get replicaset` | Prikaz ReplicaSet resursa kojima Deployment upravlja. |
| `kubectl.exe get pod` | Prikaz svih Pod-ova. |
| `kubectl.exe describe pod <ime-poda>` | Detaljne informacije i događaji za izabrani Pod. |
| `kubectl.exe get deployment <naziv-deployment-a> -o yaml` | Prikaz definicije Deployment-a u YAML formatu. |
| `kubectl.exe exec -it <ime-poda> -- /bin/bash` | Otvaranje Bash terminala unutar Pod-a. |
| `kubectl.exe get service` | Prikaz svih Service resursa. |
| `kubectl.exe describe service <ime-servisa>` | Detaljne informacije o izabranom Service-u. |
| `kubectl.exe get pod -o wide` | Prikaz dodatnih podataka, uključujući IP adrese Pod-ova. |
| `netstat.exe -a` | Prikaz svih zauzetih odnosno aktivnih portova na računaru. |

Da bi pristupio servisima spolja (npr. iz Postman-a), najlakše je port-forward:

```bash
kubectl port-forward svc/auth-service 5001:5001
kubectl port-forward svc/employee-service 5002:5002
kubectl port-forward svc/director-service 5003:5003
```

## Napomene / pretpostavke koje sam napravio

- **Nazivi image-a**: pretpostavio sam lokalni build (`auth-service:latest` itd.) sa
  `imagePullPolicy: IfNotPresent`, što Docker Desktop Kubernetes može da koristi iz
  lokalnog image skladišta. Ako pushuješ na neki
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
