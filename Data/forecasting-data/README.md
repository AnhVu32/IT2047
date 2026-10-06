forecasting-data input: Final_Data.xlsx

forecasting-data output: Processed and usable data for forecasting

# I. Review the fields used in Final_Data.xlsx

The source contains 3,037 records and 50 fields. The fields are grouped below
by their role in the forecasting pipeline.

## 1. Field decisions

### Fields retained after Step 2

| Field | Data-processing impact / procedure |
| --- | --- |
| `listing_id` | Keep as a string for duplicate removal and record tracking. Do not use it as a model feature. |
| `property_type` | Keep as a categorical model feature. |
| `area` | Convert to numeric and validate malformed or implausible values. |
| `latitude_longitude` | Split into numeric `latitude` and `longitude`; remove coordinates outside HCMC in Step 2. |
| `district` | Keep as a categorical location feature. Current values represent wards/communes and are considered reliable. |
| `bedrooms` | Convert to numeric; remove records with missing values in Step 2. |
| `legal_status` | Keep as a categorical feature and preserve `Không rõ` as an explicit category. |
| `price_range` | Keep as the target price in billion VND. Never use it as an input feature. |

### Field removed in Step 2

| Field | Data-processing impact | Data-processing procedure |
| --- | --- | --- |
| `furnishing` | Missing or unmatched raw values may have been converted into valid-looking categories. | Remove in step 2 because this field is not reliable. |

### Fields removed in Step 1

| Group | Fields | Data-processing impact | Data-processing procedure |
| --- | --- | --- | --- |
| Listing and collection metadata | `listing_type`, `posted_date`, `expiry_date`, `Folder` | Describes publication or collection rather than the physical property. | Remove in step 1 because this field is not reliable. |
| Constant field | `city_province` | Contains only `Hồ Chí Minh`, so it provides no model signal. | Remove in step 1 because this field is not reliable. |
| Raw text and address metadata | `title`, `description`, `address`, `old_address`, `location_link` | High-cardinality raw values; title and description also contain target-price leakage. | Remove in step 1 because this field is not reliable. |
| Unverified or incomplete numeric fields | `area_price_history`, `bathrooms`, `frontage`, `access_road` | Contains undocumented, sparse, malformed, or property-type-dependent values. | Remove in step 1 because this field is not reliable. |
| Sparse direction fields | `balcony_direction`, `house_direction` | Most records are missing these values. | Remove in step 1 because this field is not reliable. |
| Text-derived amenity, proximity, and view flags | `pool`, `gym`, `park`, `bbq`, `kids_playground`, `sports_court`, `security_24h`, `reception`, `elevator`, `parking`, `near_metro`, `near_bus`, `near_highway`, `near_school`, `near_hospital`, `near_mall`, `near_market`, `near_park`, `river_view`, `park_view`, `city_view`, `balcony`, `garden`, `garage`, `terrace` | A value of `0` may mean “not mentioned” rather than confirmed absence, and proximity thresholds are undocumented. | Remove in step 1 because this field is not reliable. |

## 2. Data processing pipeline
### Step 1: Remove unreliable features

Keeping only:

0. listing_id: keep for tracking purposes
1. property_type
2. area: keep with strict validation because several existing values are malformed.
3. latitude_longitude: split into numeric latitude and longitude and use corrected graph-ready coordinates.
4. district: highly reliable, informative
5. bedrooms: keep, but remove 11.2% missing rows.
6. legal_status: keep with an Unknown option
7. furnishing: keep, but need review
8. price_range: target price

Implement in directory step-1/

Step 1 creates a reduced forecasting dataset from Final_Data.xlsx.
- Keeps 8 selected input features, listing_id, and the price_range target.
- Splits latitude_longitude into numeric latitude and longitude.
- Converts numeric fields where possible.
- Preserves all 3,037 records without correcting missing or suspicious values.
- Outputs step-1/reliable_features.xlsx.

### Step 2: Clean up and verify the unreliable fields
1. Remove duplicated records
2. Remove the properties with latitude or longitude outside of HCM city
3. Remove the properties with unknown bedrooms
4. Remove furnishing because it is unreliable
5. Outputs step-2/cleaned_data.xlsx.

### Step 3: Remove outliers by property type
1. Separate records by property type: Căn hộ (apartments) and Nhà đất (houses/land).
2. Filter outliers using property-specific residential boundaries (area, bedrooms, price_range, and price per m2).
3. Combine into a clean, complete dataset with zero missing values.
4. Outputs step-3/outliers_removed.xlsx.

### Step 4: Encode categoricals and feature engineering
1. Engineer area_per_bedroom = area / bedrooms.
2. Transform price_range to log_price via log1p.
3. One-hot encode property_type, legal_status, and district.
4. Outputs step-4/encoded_data.xlsx.