"""
Entrypoint for the Shipping RabbitMQ consumer (LAB 4).

Run it as a separate process from the REST API:

    python consumer_main.py
"""

from app.events.consumer import main

if __name__ == "__main__":
    main()
