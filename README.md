# Sistem za upravljanje investicionim fondom

Kompletan sistem za upravljanje investicionim fondom implementiran sa Python/Flask, Kubernetes, PostgreSQL, MongoDB, Redis i blockchain tehnologijom.

## 📋 Preduslovi

Instalacija sledećih alata je obavezna:

- **Docker Desktop** - za build i pokretanje kontejnera
- **Docker Desktop Kubernetes** - lokalni Kubernetes klaster (omogućiti u Docker Desktop: **Settings > Kubernetes > Enable Kubernetes**)
- **kubectl** - Kubernetes command-line alat
- **Python 3.11+** - za pokretanje testova
- **pip** - Python package manager

### Provjera instalacije

```bash
docker --version
kubectl version --client
kubectl config current-context
python --version
```

## 🚀 Brzi početak

### 1. Kloniranje repozitorijuma

```bash
cd /Volumes/DodatniProstorZaMac/IEP/Projekat
```

### 2. Pokretanje Kubernetes klastera u Docker Desktop-u

```bash
# U Docker Desktop-u omogućite: Settings > Kubernetes > Enable Kubernetes.
# Sačekajte da status Kubernetes-a postane "Running", pa proverite klaster.
kubectl get nodes
```

### 3. Build Docker slika

```bash
# Docker Desktop Kubernetes koristi lokalno Docker Desktop image skladište,
# zato nije potrebno učitavanje slika u poseban klaster.
# Buildajte sve slike.
docker build -t auth-service:latest ./auth_service
docker build -t director-service:latest ./director-service
docker build -t employee-service:latest ./employee-service
docker build -t report-service:latest ./report-service
docker build -t report-service-3:latest ./report-service-3
```

### 4. Primjena Kubernetes konfiguracija

```bash
cd k8s

# Primjena svih konfiguracija redom
kubectl apply -f secret.yaml
kubectl apply -f configmap.yaml
kubectl apply -f auth-db.yaml
kubectl apply -f mongo-db.yaml
kubectl apply -f redis.yaml
kubectl apply -f blockchain.yaml
kubectl apply -f auth-service.yaml
kubectl apply -f director-service.yaml
kubectl apply -f employee-service.yaml
kubectl apply -f report-service.yaml
kubectl apply -f report-service-3.yaml
```

### 5. Čekanje da se podovi pokrenu

```bash
# Provjerite status podova
kubectl get pods

# Čekajte dok se svi pokažu kao "Running" (1-2 minuta)
```

### 6. Pokretanje port-forward tunela

U **četiri odvojena terminala**, pokrenite:

**Terminal 1:**
```bash
kubectl port-forward svc/auth-service 5801:5001
```

**Terminal 2:**
```bash
kubectl port-forward svc/employee-service 5802:5002
```

**Terminal 3:**
```bash
kubectl port-forward svc/director-service 5803:5003
```

**Terminal 4:**
```bash
kubectl port-forward svc/blockchain 58549:8545
```

**Terminal 5 (report servisi):**
```bash
kubectl port-forward svc/report-service 5804:5200
kubectl port-forward svc/report-service-3 5805:5300
```

### 7. Očistite bazu podataka (prije testiranja)

```bash
# Obriši sve korisnike iz auth DB osim direktora
kubectl exec auth-db-7689ffb55b-v6wtq -- psql -U auth_user -d auth_db -c "DELETE FROM users WHERE email != 'onlymoney@gmail.com';"

# Obriši sve assets iz MongoDB
kubectl exec mongo-db-849cccf94d-wrm42 -- mongosh fond_db --eval "db.assets.deleteMany({})"

# Isprazni Redis
kubectl exec redis-service-5b45dc96cc-g6x6m -- redis-cli FLUSHALL
```

### 8. Pokrenite grader testove

```bash
cd /Volumes/DodatniProstorZaMac/IEP/Projekat
source .venv/bin/activate
cd tests/iep_grader

# Instalacija test zavisnosti (prvi put)
pip install -q -r requirements.txt -r requirements-pytest.txt

# Pokretanje testova
python -m pytest -q test_grader.py \
  --type all \
  --with-authentication \
  --authentication-url http://localhost:5801 \
  --jwt-secret super-tajni-kljuc-promeni-ovo \
  --roles-field role \
  --employee-role employee \
  --director-role director \
  --employee-url http://localhost:5802 \
  --director-url http://localhost:5803 \
  --with-blockchain \
  --provider-url http://localhost:58549 \
  --grade-report-file grade_report.json
```

Testovi bi trebalo da se završe za ~30 sekundi i pokažu:
```
============================= IEP grading summary ==============================
authentication: 49.00/49.00 (100.00%)
level0: 27.00/27.00 (100.00%)
level1: 25.00/25.00 (100.00%)
level2: 29.00/29.00 (100.00%)
level3: 49.00/49.00 (100.00%)
TOTAL: 179.00/179.00 (100.00%)
```

## 📁 Struktura projekta

```
Projekat/
├── auth_service/                 # Servis za autentifikaciju
│   ├── app.py                   # Flask aplikacija
│   ├── requirements.txt          # Python zavisnosti
│   └── Dockerfile               # Docker konfiguracija
│
├── employee-service/            # Servis za zaposlene
│   ├── app.py                   # Flask aplikacija
│   ├── requirements.txt          # Python zavisnosti
│   └── Dockerfile               # Docker konfiguracija
│
├── director-service/            # Servis za direktora
│   ├── app.py                   # Flask aplikacija
│   ├── requirements.txt          # Python zavisnosti
│   └── Dockerfile               # Docker konfiguracija
│
├── report-service/              # Report servis (prost pregled assets-a)
│   ├── app.py                   # Flask aplikacija
│   ├── requirements.txt          # Python zavisnosti
│   └── Dockerfile               # Docker konfiguracija
│
├── report-service-3/            # Report servis sa MongoDB aggregation reportovima
│   ├── app.py                   # Flask aplikacija
│   ├── requirements.txt          # Python zavisnosti
│   └── Dockerfile               # Docker konfiguracija
│
├── k8s/                         # Kubernetes konfiguracije
│   ├── secret.yaml              # Tajne (lozinke, JWT ključ)
│   ├── configmap.yaml           # Konfiguracija
│   ├── auth-db.yaml             # PostgreSQL deployment
│   ├── mongo-db.yaml            # MongoDB deployment
│   ├── redis.yaml               # Redis deployment
│   ├── blockchain.yaml          # Ganache (blockchain) deployment
│   ├── auth-service.yaml        # Auth servis deployment
│   ├── director-service.yaml    # Director servis deployment
│   ├── employee-service.yaml    # Employee servis deployment (3 replike)
│   ├── report-service.yaml      # Report servis deployment
│   ├── report-service-3.yaml    # Report servis 3 (aggregation) deployment
│   └── README.md                # Kubernetes uputstvo
│
├── tests/                       # Testovi
│   ├── tests.zip                # Kompresovani testovi
│   ├── report_service_3/        # Testovi agregacionih reportova
│   └── iep_grader/              # Grader test suite
│       ├── test_grader.py       # Glavni test fajl
│       ├── requirements.txt      # Test zavisnosti
│       └── ...
│
└── README.md                    # Ovaj fajl
```

## 🔧 Konfiguracija

### Kubernetes Secret (JWT i baza podataka)

Fajl: `k8s/secret.yaml`

```yaml
stringData:
  JWT_SECRET_KEY: "super-tajni-kljuc-promeni-ovo"
  POSTGRES_USER: "auth_user"
  POSTGRES_PASSWORD: "auth_password"
  MONGO_INITDB_ROOT_USERNAME: "mongo_user"
  MONGO_INITDB_ROOT_PASSWORD: "mongo_password"
```

### Kubernetes ConfigMap

Fajl: `k8s/configmap.yaml`

Sadrži sve konfiguracije za servise:
- `MONGO_DB_NAME`: `fond_db`
- `BLOCKCHAIN_HOST`: `blockchain`
- `BLOCKCHAIN_RPC_PORT`: `8545`

## 🔐 Zavisnosti

### Auth Service
- Flask
- Flask-JWT-Extended
- Flask-SQLAlchemy
- psycopg2-binary
- email-validator

### Employee Service
- Flask
- Flask-JWT-Extended
- pymongo
- redis

### Director Service
- Flask
- Flask-JWT-Extended
- pymongo
- redis
- web3

### Report Service / Report Service 3
- Flask
- pymongo

## 📚 API Endpoints

### Auth Service (Port 5001)

- `POST /register` - Registracija novog korisnika
- `POST /login` - Prijava korisnika
- `POST /delete` - Brisanje korisnika

### Employee Service (Port 5002)

- `POST /search` - Pretraga assets-a
- `POST /create_buy_order` - Kreiranje buy order-a
- `POST /create_sell_order` - Kreiranje sell order-a

### Director Service (Port 5003)

- `GET /pending_orders` - Pregled čekajućih order-a
- `POST /decision` - Odobravanje/odbijanje order-a (sa blockchain voting-om)
- `GET /report` - Pregled izveštaja o radu fonda

### Report Service (Port 5200)

- `GET /get_all` - Pregled svih assets-a iz MongoDB-a

### Report Service 3 (Port 5300)

Servis je napravljen po uzoru na postojeći report servis, ali svi reportovi
koriste MongoDB `aggregate` interfejs nad kolekcijom `assets`.

| Endpoint | Opis | Ključni stage-ovi |
| --- | --- | --- |
| `GET /aggregate/summary` | Zbirni pregled fonda (uloženo, zarađeno, profit, raspodela po statusu, najskuplja imovina) | `$addFields`, `$facet`, `$group`, `$sortByCount`, `$sort`, `$limit`, `$count`, `$replaceWith` |
| `GET /aggregate/by_category?skip=0&limit=10` | Statistika po kategorijama sa ROI procentom i paginacijom | `$unwind`, `$group`, `$addFields`, `$sort`, `$skip`, `$limit`, `$project` |
| `GET /aggregate/category_counts` | Broj pojavljivanja svake kategorije | `$unwind`, `$sortByCount` |
| `GET /aggregate/top_profit?limit=10` | Najprofitabilnija prodata imovina i broj dana držanja | `$match`, `$addFields`, `$dateDiff`, `$sort`, `$limit` |
| `GET /aggregate/price_buckets` | Raspodela imovine po cenovnim rangovima (fiksni i automatski) | `$match`, `$facet`, `$bucket`, `$bucketAuto` |
| `GET /aggregate/monthly_activity` | Kupovine grupisane po mesecu | `$addFields`, `$dateFromString`, `$group`, `$dateToString`, `$sort` |
| `GET /aggregate/info_keys` | Najčešći ključevi u dinamičkom `info` objektu | `$project`, `$objectToArray`, `$unwind`, `$sortByCount` |
| `GET /aggregate/category_overview` | Za svaku kategoriju lista imovine koja se još drži i njena vrednost | `$unwind`, `$group`, `$lookup` (sa `let`/`pipeline`), `$addFields`, `$sort` |
| `GET /aggregate/assets?category=Akcije&skip=0&limit=10` | Paginirana lista imovine sa izvedenim statusom i profitom | `$match`, `$addFields`, `$sort`, `$skip`, `$limit`, `$project`, `$count` |

Primeri:

```bash
curl http://localhost:5805/aggregate/summary
curl "http://localhost:5805/aggregate/by_category?skip=0&limit=5"
curl "http://localhost:5805/aggregate/top_profit?limit=3"
curl "http://localhost:5805/aggregate/assets?category=Tehnologija&limit=2"
```

Lokalno pokretanje bez Kubernetes-a:

```bash
cd report-service-3
pip install -r requirements.txt
MONGO_HOST=localhost MONGO_PORT=27017 MONGO_DB_NAME=fond_db python app.py
```

Testovi (potreban je dostupan MongoDB, npr. `docker run -d -p 27017:27017 mongo:6.0`):

```bash
python -m pytest tests/report_service_3 -q
```

## 🔍 Troubleshooting

### Problem: Podovi ne kreće se

```bash
# Proverite status podova
kubectl get pods

# Pogledajte logove
kubectl logs <pod-name>

# Provjerite event-e
kubectl describe pod <pod-name>
```

### Problem: Port-forward se prekida

Ponovo pokrenite:
```bash
kubectl port-forward svc/<service-name> <local-port>:<service-port>
```

### Problem: Testovi padaju zbog starog stanja

Očistite bazu:
```bash
kubectl exec auth-db-7689ffb55b-v6wtq -- psql -U auth_user -d auth_db -c "DELETE FROM users WHERE email != 'onlymoney@gmail.com';"
kubectl exec mongo-db-849cccf94d-wrm42 -- mongosh fond_db --eval "db.assets.deleteMany({})"
kubectl exec redis-service-5b45dc96cc-g6x6m -- redis-cli FLUSHALL
```

### Problem: Docker build ne radi

```bash
# Očistite Docker cache
docker system prune -a

# Provjerite da su fajlovi na mjestu
ls -la auth_service/requirements.txt
ls -la director-service/requirements.txt
ls -la employee-service/requirements.txt
```

## 📊 Očekivani rezultati

Nakon što su svi testovi prošli sa 100%, grader report se nalazi u:
```
tests/iep_grader/grade_report.json
```

## 🛑 Zaustavljanje sistema

```bash
# Obriši sve Kubernetes resurse
kubectl delete all --all

# Za potpuno gašenje klastera, u Docker Desktop-u isključite
# Settings > Kubernetes > Enable Kubernetes.
```

## 📝 Napomene

- **JWT Token**: Validan je 1 sat
- **Blockchain**: Koristi Ganache sa 10 pré-generisanih računa
- **Database**: PostgreSQL za auth, MongoDB za assets
- **Cache**: Redis za voting sesije
- **Voting**: Blockchain-bazirano glasanje sa većinskom odlukom

## 👨‍💻 Podrška

Za probleme ili pitanja, provjerite:
1. Kubernetes logove: `kubectl logs <pod-name>`
2. Port-forward konekcije: `curl http://localhost:5801/login`
3. Status podova: `kubectl get pods -o wide`

---

**Verzija**: 1.0  
**Posljednja ažuriranja**: August 2, 2026
