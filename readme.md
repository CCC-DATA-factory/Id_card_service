# 🇹🇳 Unified Tunisian ID Service

This service provides an API for validation, extracting and translating personal information from **Tunisian ID card images** using **LLM**. It supports:
- font/back id card validation
- font/back id card information extracting
- Transliteration and translation from Arabic to Latin/English
- Batch processing
- Dynamic API keys rotation and management

---

## 🚀 Features
- 🖼️ Invalid Card Detection: Can identify if an uploaded image is not a Tunisian ID card front/back.
- 🖼️ Extract structured informations from front or back side of Tunisian ID card images
- 🔤 Arabic → Latin/English transliteration & translation
- 🔄 Handles multiple API keys and rotates on failure
- 📦 Available as a Python service or Docker container

---

## ⚙️ Setup Instructions

### Option 1: Run with Python

#### 1. Clone the repository

```bash
git clone https://github.com/your-org/unified-tunisian-id-service.git
cd Id_card_service
```
#### 2. Install dependencies
```bash
python3 -m venv venv
venv/bin/activate
pip install -r requirements.txt
```
#### 3. Create your api_keys.env file
```env
GOOGLE_API_KEY_1=your_first_api_key
GOOGLE_API_KEY_2=your_second_api_key
```
You can also manage keys dynamically using the /add_api_key endpoint.

#### 4. Start the service
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
### Option 2: Run with Docker

#### 1. Build and run the service
```bash
docker-compose up --build
```
Ensure your docker-compose.yml and api_keys.env files are in the root directory.

## 📡 API Endpoints
Base URL: http://localhost:8000

### `GET /Health check.`

Returns:

```json

{
  "message": "Unified Tunisian ID service is running."
}
```
### `POST /transcript`

Batch process structured Arabic data to return transliterated/translated Tunisian ID card data.

Request Body: (JSON array of objects)

```json
[
  {
    "idNumber": "-sensitive_information-",
    "lastName": "دبوسي",
    "firstName": "فاروق",
    "fatherFullName": "بن جمال بن علي",
    "dateOfBirth": "21 ديسمبر 1999",
    "placeOfBirth": "تونس",
    "motherFullName": "سامية المنصور",
    "job": "تلميذ",
    "address": "10 نهج 9 أفريل اريانة",
    "dateOfCreation": "26 اوت 2017"
  }
]
```
Returns:

- 200 OK with list of transliterated/transformed JSON objects
```json
[
    {
        "idNumber": "-sensitive_information-",
        "lastName": "Dabbousi",
        "firstName": "Farouk",
        "fatherFullName": "Ben Jamal Ben Ali",
        "dateOfBirth": "1999/12/21",
        "placeOfBirth": "Tunis",
        "motherFullName": "Samia Mansour",
        "job": "Student",
        "address": "10, 9 April Street, Ariana",
        "dateOfCreation": "2017/08/26"
    }
]
```

- 500 Internal Server Error if processing fails


### `POST /front`

Upload an image of the front side of a Tunisian ID card to extract fields.

- Form-data: image: JPG or PNG file

Returns:

- 200 OK on success

```json

{
    "idNumber": "-sensitive_information-",
    "lastName": "دبوسي",
    "firstName": "فاروق",
    "fatherFullName": "بن جمال بن علي",
    "dateOfBirth": "21 ديسمبر 1999",
    "placeOfBirth": "تونس"
}
```


- 400 Bad Request if invalid ID card

```json
{
    "detail": "Failed after retries: 400: Invalid ID card"
}
```
- 500 Internal Server Error on processing failure ( could be inclear id card or not valid)


### `POST /back`
Upload an image of the back side of a Tunisian ID card to extract fields.

Form-data:

- image: JPG or PNG file

Returns:

- 200 OK on success

```json

{
    "motherFullName": "سامية المنصور",
    "job": "تلميذ",
    "address": "10 نهج 9 أفريل اريانة",
    "dateOfCreation": "26 اوت 2017"
}
```

- 400 Bad Request if invalid ID card
```json
{
    "detail": "Failed after retries: 400: Invalid ID card"
}
```

- 500 Internal Server Error on processing failure ( could be inclear id card or not valid)

### POST /add_api_key
Add a new Gemini API key at runtime.

Request Body:

```json

{
  "api_key": "your-new-api-key"
}
```
Returns:

```json

{
  "message": "API key added successfully.",
  "total_keys": 3
}
```
Status Codes:

- 200 OK if added

- 500 Internal Server Error on failure

## 🧠 How It Works
Images or structured JSON data are passed to the Gemini model.

Prompts guide the LLM to:

Extract fields (e.g., names, dates, addresses)

Translate Arabic to English

Transcribe Arabic names using Tunisian Latin standards

Data is validated with Pydantic models

## 📝 Notes

- The transliteration and translation provided by this service may not be fully accurate and should be reviewed by a human agent for verification.

- An ID card is only considered valid if all required fields are successfully extracted; otherwise, it will be flagged as invalid.

- The retry mechanism, which ensures robustness across multiple API keys, may slightly increase response times.

- The POST /transcript endpoint expects a list of ID card data objects, not a single object. This design enables batch processing of multiple ID cards in one request, improving efficiency and performance.
