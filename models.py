from dataclasses import dataclass


@dataclass
class ParsedOffer:
    source_url: str
    hotel_url: str
    hotel_name: str
    departure_city: str
    arrival_country: str
    price: int
    book_url: str
    details: str
