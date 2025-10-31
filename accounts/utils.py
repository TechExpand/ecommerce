import os
import requests

def send_email(email: str, subject: str, template: str):
    """
    Sends an email using the Brevo (formerly Sendinblue) SMTP API.
    """
    url = "https://api.brevo.com/v3/smtp/email"
    api_key = os.getenv("BREVO")  # your Brevo API key from environment variables

    payload = {
        "sender": {
            "name": "Easy Money Broker",
            "email": "dailydevo9+mcl@gmail.com"
        },
        "to": [
            {
                "email": email,
                "name": "User"
            }
        ],
        "subject": subject,
        "htmlContent": template
    }

    headers = {
        "api-key": api_key,
        "accept": "application/json",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()  # raises an error for 4xx/5xx responses

        return {
            "status": True,
            "message": response.json()
        }

    except requests.exceptions.RequestException as e:
        print("Error sending email:", e)
        return {
            "status": False,
            "message": str(e)
        }
