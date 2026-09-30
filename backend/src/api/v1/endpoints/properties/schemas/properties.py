from typing import Union, Optional
from pydantic import BaseModel, Field


class PackageResponseModel(BaseModel):
    ip_address: Optional[str] = Field(None, description="IPv4")
    city: Optional[str] = Field(None, description="City")
    region: Optional[str] = Field(None, description="Region")
    country: Optional[str] = Field(None, description="Country")
    latitude: Optional[float] = Field(None, description="Latitude")
    longitude: Optional[float] = Field(None, description="Longitude")

class AddPackageModel(BaseModel):
    ip_address: Optional[str] = Field(None, description="IPv4")
    city: Optional[str] = Field(None, description="City")
    region: Optional[str] = Field(None, description="Region")
    country: Optional[str] = Field(None, description="Country")
    latitude: Optional[float] = Field(None, description="Latitude")
    longitude: Optional[float] = Field(None, description="Longitude")

class AISearchRequestModel(BaseModel):
    question: str = Field(None, description="Search keyword in title, description or address")
    min_price: float = Field(None, description="Minimum price (billion VND)")
    max_price: float = Field(None, description="Maximum price (billion VND)")
    min_area: float = Field(None, description="Minimum area (square meters)")
    max_area: float = Field(None, description="Maximum area (square meters)")
    bedrooms: int = Field(None, description="Number of bedrooms")
    bathrooms: int = Field(None, description="Number of bathrooms")
    legal_status: str = Field(None, description="Legal status of property (e.g. pink book, notarized contract)")
    furniture: str = Field(None, description="Furniture status (e.g. fully furnished, basic, unfurnished)")
    house_direction: str = Field(None, description="Main house direction (e.g. North, South, East, West)")
    balcony_direction: str = Field(None, description="Balcony direction")
    length_road_entrance: float = Field(None, description="Length of road entrance (meters)")

    district: str = Field(None, description="District name (e.g. District 1, Binh Thanh)")
    # Boolean feature filters (frontend may send 0/1; backend treats only truthy as requested)
    pool: Optional[bool] = Field(None, description="Filter by pool availability")
    gym: Optional[bool] = Field(None, description="Filter by gym availability")
    park: Optional[bool] = Field(None, description="Filter by park availability")
    bbq: Optional[bool] = Field(None, description="Filter by BBQ area availability")
    kids_playground: Optional[bool] = Field(None, description="Filter by kids playground availability")
    sports_court: Optional[bool] = Field(None, description="Filter by sports court availability")
    security_24h: Optional[bool] = Field(None, description="Filter by 24h security availability")
    reception: Optional[bool] = Field(None, description="Filter by reception availability")
    elevator: Optional[bool] = Field(None, description="Filter by elevator availability")
    parking: Optional[bool] = Field(None, description="Filter by parking availability")

    near_metro: Optional[bool] = Field(None, description="Filter by near metro")
    near_bus: Optional[bool] = Field(None, description="Filter by near bus")
    near_highway: Optional[bool] = Field(None, description="Filter by near highway")
    near_school: Optional[bool] = Field(None, description="Filter by near school")
    near_hospital: Optional[bool] = Field(None, description="Filter by near hospital")
    near_mall: Optional[bool] = Field(None, description="Filter by near mall")
    near_market: Optional[bool] = Field(None, description="Filter by near market")
    near_park: Optional[bool] = Field(None, description="Filter by near park")

    river_view: Optional[bool] = Field(None, description="Filter by river view")
    park_view: Optional[bool] = Field(None, description="Filter by park view")
    city_view: Optional[bool] = Field(None, description="Filter by city view")

    balcony: Optional[bool] = Field(None, description="Filter by balcony availability")
    garden: Optional[bool] = Field(None, description="Filter by garden availability")
    garage: Optional[bool] = Field(None, description="Filter by garage availability")
    terrace: Optional[bool] = Field(None, description="Filter by terrace availability")