# unity-home-task

1. install and start minikube
brew install minikube 
minikube start --driver=docker --container-runtime=containerd


2. install kafka on k8s
kubectl create namespace kafka
kubectl create -f 'https://strimzi.io/install/latest?namespace=kafka' -n kafka
kubectl apply -f https://strimzi.io/examples/latest/kafka/kafka-single-node.yaml -n kafka

2.1 validate kafka is running
kubectl get pods -n kafka
kubectl get services -n kafka


3. deploy mongo and mongo sevice on k8s
kubectl apply -f mongo-db
kubectl apply -f mongo-headless-svc.yaml

3. build image/ tag locally for customer-management and load into minikube 
cd customer-management
docker build -t customer-management:v2.0.5 .	
minikube image load customer-management:v2.0.5
cd ..
kubectl apply -f customer-management.yaml

4. build image/ tag locally for web-server and load into minikube 
cd web-server
docker build -t web-servert:v2.0.4 .	
minikube image load web-server:v2.0.4
cd ..
kubectl apply -f web-server.yaml

-------------------------------------------------------------

runnin and testing

1. start port-foward to web-server:
kubectl port-forward svc/web-server 3000:3000

2. create new purchases  

 curl -X POST http://localhost:3000/buy \
  -H "Content-Type: application/json" \
  -d '{"username":"bar","userid":"001","price":17.5}'

 curl -X POST http://localhost:3000/buy \
  -H "Content-Type: application/json" \
  -d '{"username":"dan","userid":"002","price":18.5}'

3. query buyers
curl "http://localhost:3000/getAllUserBuys?userid=001"
curl "http://localhost:3000/getAllUserBuys?userid=002"


4.  query mongo-db
kubectl exec -it mongo-0 -n default -- bash
mongosh "mongodb://localhost:27017"
use purchases_db
db.purchases.find()

5. query kafka
kubectl exec -it my-cluster-dual-role-0 -n kafka -- /bin/bash

./bin/kafka-console-consumer.sh \
  --bootstrap-server my-cluster-kafka-bootstrap.kafka.svc.cluster.local:9092 \
  --topic purchases \
  --from-beginning
