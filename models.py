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
    rating: float = 0.0
    stars: int = 0
    nights: int = 0
    meal_type: str = ""
    adults: int = 0
    departure_date: str = ""
    return_date: str = ""
