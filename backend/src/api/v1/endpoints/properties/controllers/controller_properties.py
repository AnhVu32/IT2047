from starlette import status


from src.api.base.controller import BaseController
from src.api.v1.endpoints.properties.repositories.repo_properties import (
    repo_get_properties,
    repo_add_log,
)
from src.settings.event import recommendation_service


class PropertiesController(BaseController):
    async def ctr_get_properties(
        self,
        query: str,
        min_price: float,
        max_price: float,
        min_area: float,
        max_area: float,
        bedrooms: int,
        bathrooms: int,
        legal_status: str,
        furniture: str,
        house_direction: str,
        balcony_direction: str,
        min_frontage: float,
        min_road_width: float,
        sort_by: str,
        sort_order: str,
        page: int,
        limit: int,
        property_type: str,
        district: str = None,
        pool: bool = None,
        gym: bool = None,
        park: bool = None,
        bbq: bool = None,
        kids_playground: bool = None,
        sports_court: bool = None,
        security_24h: bool = None,
        reception: bool = None,
        elevator: bool = None,
        parking: bool = None,
        near_metro: bool = None,
        near_bus: bool = None,
        near_highway: bool = None,
        near_school: bool = None,
        near_hospital: bool = None,
        near_mall: bool = None,
        near_market: bool = None,
        near_park: bool = None,
        river_view: bool = None,
        park_view: bool = None,
        city_view: bool = None,
        balcony: bool = None,
        garden: bool = None,
        garage: bool = None,
        terrace: bool = None,
    ):
        """
        Controller to get list of properties for listing page.
        Currently returns dummy data from repository layer.
        """
        try:
            if page < 1 and limit < 1:
                self.errors.append(
                    {
                        "loc": "PropertiesController -> ctr_get_properties",
                        "msg": "Page and limit must be greater than 0",
                        "detail": "Page and limit must be greater than 0",
                    }
                )
                return self.response(data=None, status_code=status.HTTP_400_BAD_REQUEST)
            
            is_success, data, error = repo_get_properties(
                query=query,
                min_price=min_price,
                max_price=max_price,
                min_area=min_area,
                max_area=max_area,
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                legal_status=legal_status,
                furniture=furniture,
                house_direction=house_direction,
                balcony_direction=balcony_direction,
                min_frontage=min_frontage,
                min_road_width=min_road_width,
                sort_by=sort_by,
                sort_order=sort_order,
                page=page,
                limit=limit,
                property_type=property_type,
                district=district,
                pool=pool,
                gym=gym,
                park=park,
                bbq=bbq,
                kids_playground=kids_playground,
                sports_court=sports_court,
                security_24h=security_24h,
                reception=reception,
                elevator=elevator,
                parking=parking,
                near_metro=near_metro,
                near_bus=near_bus,
                near_highway=near_highway,
                near_school=near_school,
                near_hospital=near_hospital,
                near_mall=near_mall,
                near_market=near_market,
                near_park=near_park,
                river_view=river_view,
                park_view=park_view,
                city_view=city_view,
                balcony=balcony,
                garden=garden,
                garage=garage,
                terrace=terrace,
            )
            if not is_success:
                self.errors.append(
                    {
                        "loc": "PropertiesController -> ctr_get_properties",
                        "msg": error,
                        "detail": error,
                    }
                )
                return self.response(
                    data=None, status_code=status.HTTP_400_BAD_REQUEST
                )

            return self.response(data=data, status_code=status.HTTP_200_OK)
        except Exception as e:
            self.errors.append(
                {
                    "loc": "PropertiesController -> ctr_get_properties",
                    "msg": "Internal server error",
                    "detail": str(e),
                }
            )
            return self.response(
                data=None, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    async def ctr_ai_search(
        self,
        question: str,
        min_price: float,
        max_price: float,
        min_area: float,
        max_area: float,
        bedrooms: int,
        bathrooms: int,
        legal_status: str,
        furniture: str,
        house_direction: str,
        balcony_direction: str,
        length_road_entrance: float,
        district: str = None,
        pool: bool = None,
        gym: bool = None,
        park: bool = None,
        bbq: bool = None,
        kids_playground: bool = None,
        sports_court: bool = None,
        security_24h: bool = None,
        reception: bool = None,
        elevator: bool = None,
        parking: bool = None,
        near_metro: bool = None,
        near_bus: bool = None,
        near_highway: bool = None,
        near_school: bool = None,
        near_hospital: bool = None,
        near_mall: bool = None,
        near_market: bool = None,
        near_park: bool = None,
        river_view: bool = None,
        park_view: bool = None,
        city_view: bool = None,
        balcony: bool = None,
        garden: bool = None,
        garage: bool = None,
        terrace: bool = None,
    ):
        """
        Controller to get AI search.
        """
        try:
            is_success, data_response, error = await recommendation_service.ai_recommendation(
                question=question,
                min_price=min_price,
                max_price=max_price,
                min_area=min_area,
                max_area=max_area,
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                legal_status=legal_status,
                furniture=furniture,
                house_direction=house_direction,
                balcony_direction=balcony_direction,
                length_road_entrance=length_road_entrance,
                district=district,
                pool=pool,
                gym=gym,
                park=park,
                bbq=bbq,
                kids_playground=kids_playground,
                sports_court=sports_court,
                security_24h=security_24h,
                reception=reception,
                elevator=elevator,
                parking=parking,
                near_metro=near_metro,
                near_bus=near_bus,
                near_highway=near_highway,
                near_school=near_school,
                near_hospital=near_hospital,
                near_mall=near_mall,
                near_market=near_market,
                near_park=near_park,
                river_view=river_view,
                park_view=park_view,
                city_view=city_view,
                balcony=balcony,
                garden=garden,
                garage=garage,
                terrace=terrace,
            )
            
            if not data_response:
                self.errors.append(
                    {
                        "loc": "PropertiesController -> ctr_ai_search",
                        "msg": "Không tìm thấy căn hộ phù hợp",
                        "detail": "Không tìm thấy căn hộ phù hợp",
                    }
                )
                return self.response(data=None, status_code=status.HTTP_400_BAD_REQUEST)
            
            repo_add_log(
                user_id=None,
                action="ai_search",
                content="Lấy kết quả từ embedding search",
                metadata={
                    "data_response": data_response, 
                },
            )
            return self.response(data=data_response, status_code=status.HTTP_200_OK)
        except Exception as e:
            self.errors.append(
                {
                    "loc": "PropertiesController -> ctr_ai_search",
                    "msg": "Internal server error",
                    "detail": str(e),
                }
            )
            return self.response(data=None, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
