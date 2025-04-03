# ArtMarket Cloud Application

ArtMarket is a scalable cloud native web application
that helps digital artists gauge and validate their art via interact-
ing frontend and backend services that it provides. This system
allows users to upload digital images and receive an immediate
feedback, including current market price, authenticity status,
geolocation and currency conversion for a particular location. It
is a platform that combines four different APIs; a Price Predict
API made by the self, an Authentication API ment created by
the other and the two public APIs for Geolocation which is IP
based and Currency Exchange Rate. AWS Lambda is used to
deploy backend APIs that are exposed through API Gateway for
a stateless and serverless architecture. It is hosted on AWS Elastic
Beanstalk, with automating deployment using AWS CodePipeline.
These components together create a fully moduler, scalable and
cloud optimized solution specific for the digital art domain.This
is a set of fully moduler, scalable and cloud optimized solution
for the digital art domain.

##  APIs Integrated

| Purpose            | Type     | URL                                                                 
|  Price Prediction| Private (Yours)  `https://gi96frqbc5.execute-api.eu-west-1.amazonaws.com`               
| Art Authentication | Classmate API    `https://rf83t8chb1.execute-api.eu-west-1.amazonaws.com`               
|  Geo Location     | Public           `https://ipapi.co/json/`                                              
|  Currency Rates   | Public           `https://api.exchangerate-api.com/v4/latest/USD`


## Setup Instructions

1. **Clone Repository**
2. git clone https://github.com/RahulShirsat003/ArtWork.git
3. pip install -r requirements.txt
4. python application.py   
5. App will be available at http://localhost:8080

## Author
	•	Name: Rahul Shirsat
	•	Module: Scalable Cloud Programming
	•	University: National College of Ireland
 
 
