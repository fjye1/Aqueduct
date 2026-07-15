from sqlalchemy import Column, String, Integer, Float, ForeignKey, UniqueConstraint
from sync.database import Base


class Borough(Base):
    __tablename__ = "boroughs"

    ons_code = Column(String(10), primary_key=True, index=True)
    name = Column(String(100), nullable=False)

# TODO Write 6 tables infra, education, housing, housing_historical, police, police_historical

# =====================================================================
# 1 OF 4: DOMAIN STATIC TABLES (Education)
# =====================================================================


class BoroughEducation(Base):
    __tablename__ = "borough_education"

    # Links 1:1 to the main boroughs table
    ons_code = Column(String(10), ForeignKey("boroughs.ons_code"), primary_key=True)

    # Raw stats & Counts
    independent_pupil_capacity = Column(Float)
    independent_current_pupils = Column(Float)
    independent_school_count = Column(Float)

    public_funded_pupil_capacity = Column(Float)
    public_funded_current_pupils = Column(Float)

    # School Type Counts
    public_funded_nursery = Column(Integer, default=0)
    public_funded_primary = Column(Integer, default=0)
    public_funded_secondary = Column(Integer, default=0)
    public_funded_school_count = Column(Integer, default=0)
    total_school_count = Column(Float, default=0.0)

    # Quality Averages (Ofsted Metrics)
    avg_quality_of_education = Column(Float)
    avg_behaviour_and_attitudes = Column(Float)
    avg_personal_development = Column(Float)
    avg_effectiveness_of_leadership_and_management = Column(Float)

    # Precomputed Percentages/Ratios
    pct_of_total_schools_private = Column(Float)
    public_funded_pct_capacity_filled = Column(Float)


# =====================================================================
# 2 OF 4: DOMAIN STATIC TABLES (Housing - Current State)
# =====================================================================
class BoroughHousing(Base):
    __tablename__ = "borough_housing"

    # Links 1:1 to the main boroughs table for the most recent year's data
    ons_code = Column(String(10), ForeignKey("boroughs.ons_code"), primary_key=True)
    year = Column(Integer)

    # Raw stats
    total_dwellings = Column(Integer)
    affordable_additions = Column(Float)
    band_d = Column(Integer)
    average_price = Column(Integer)
    net_additions = Column(Float)

    # Precomputed London Averages
    lon_average_price = Column(Float)
    lon_avg_affordable_additions = Column(Float)
    lon_avg_total_dwellings = Column(Float)
    lon_avg_net_additions = Column(Float)
    lon_avg_band_d = Column(Float)

    # Precomputed Percentage Differences from London Average
    pct_diff_average_price = Column(Float)
    pct_diff_affordable_additions = Column(Float)
    pct_diff_total_dwellings = Column(Float)
    pct_diff_net_additions = Column(Float)
    pct_diff_band_d = Column(Float)

    # Precomputed Year-on-Year Growth & Ratios
    yoy_pct_change_average_price = Column(Float)
    yoy_pct_change_total_dwellings = Column(Float)
    ratio_of_total_new_house_affordable = Column(Float)

# =====================================================================
# 3 OF 4: DOMAIN STATIC TABLES (Infrastructure/Transport - Current State)
# =====================================================================


class BoroughInfrastructure(Base):
    __tablename__ = "borough_infrastructure"

    # Links 1:1 to the main boroughs table
    ons_code = Column(String(10), ForeignKey("boroughs.ons_code"), primary_key=True)

    # Accessibility Metrics
    ptal = Column(String(10))
    avg_ptal = Column(Float)
    pct_diff_from_avg = Column(Float)

    # Transit Asset Counts
    bus_count = Column(Integer, default=0)
    dlr_count = Column(Integer, default=0)
    elizabeth_count = Column(Integer, default=0)
    overground_count = Column(Integer, default=0)
    tramlink_count = Column(Integer, default=0)
    tube_count = Column(Integer, default=0)

    # List of intersecting transit line names (e.g., "Northern, Piccadilly")
    line_name = Column(String(255))


# =====================================================================
# 4 OF 4: DOMAIN STATIC TABLES (Police/Crime - Current State)
# =====================================================================
class BoroughPolice(Base):
    __tablename__ = "borough_police"

    # Links 1:1 to the main boroughs table for the most recent year's data
    ons_code = Column(String(10), ForeignKey("boroughs.ons_code"), primary_key=True)
    year = Column(Integer)

    # Raw Crime Annualised Rates
    anti_social_behaviour_annualised_rate = Column(Float)
    bicycle_theft_annualised_rate = Column(Float)
    burglary_annualised_rate = Column(Float)
    criminal_damage_arson_annualised_rate = Column(Float)
    drugs_annualised_rate = Column(Float)
    other_crime_annualised_rate = Column(Float)
    other_theft_annualised_rate = Column(Float)
    possession_of_weapons_annualised_rate = Column(Float)
    public_order_annualised_rate = Column(Float)
    robbery_annualised_rate = Column(Float)
    shoplifting_annualised_rate = Column(Float)
    theft_from_the_person_annualised_rate = Column(Float)
    vehicle_crime_annualised_rate = Column(Float)
    violent_crime_annualised_rate = Column(Float)

    # Precomputed London Averages
    lon_avg_anti_social_behaviour_annualised_rate = Column(Float)
    lon_avg_bicycle_theft_annualised_rate = Column(Float)
    lon_avg_burglary_annualised_rate = Column(Float)
    lon_avg_criminal_damage_arson_annualised_rate = Column(Float)
    lon_avg_drugs_annualised_rate = Column(Float)
    lon_avg_other_crime_annualised_rate = Column(Float)
    lon_avg_other_theft_annualised_rate = Column(Float)
    lon_avg_possession_of_weapons_annualised_rate = Column(Float)
    lon_avg_public_order_annualised_rate = Column(Float)
    lon_avg_robbery_annualised_rate = Column(Float)
    lon_avg_shoplifting_annualised_rate = Column(Float)
    lon_avg_theft_from_the_person_annualised_rate = Column(Float)
    lon_avg_vehicle_crime_annualised_rate = Column(Float)
    lon_avg_violent_crime_annualised_rate = Column(Float)

    # Precomputed Percentage Differences from London Average
    pct_diff_anti_social_behaviour_annualised_rate = Column(Float)
    pct_diff_bicycle_theft_annualised_rate = Column(Float)
    pct_diff_burglary_annualised_rate = Column(Float)
    pct_diff_criminal_damage_arson_annualised_rate = Column(Float)
    pct_diff_drugs_annualised_rate = Column(Float)
    pct_diff_other_crime_annualised_rate = Column(Float)
    pct_diff_other_theft_annualised_rate = Column(Float)
    pct_diff_possession_of_weapons_annualised_rate = Column(Float)
    pct_diff_public_order_annualised_rate = Column(Float)
    pct_diff_robbery_annualised_rate = Column(Float)
    pct_diff_shoplifting_annualised_rate = Column(Float)
    pct_diff_theft_from_the_person_annualised_rate = Column(Float)
    pct_diff_vehicle_crime_annualised_rate = Column(Float)
    pct_diff_violent_crime_annualised_rate = Column(Float)

    # Precomputed Year-on-Year Growth
    yoy_pct_change_anti_social_behaviour_annualised_rate = Column(Float)
    yoy_pct_change_bicycle_theft_annualised_rate = Column(Float)
    yoy_pct_change_burglary_annualised_rate = Column(Float)
    yoy_pct_change_criminal_damage_arson_annualised_rate = Column(Float)
    yoy_pct_change_drugs_annualised_rate = Column(Float)
    yoy_pct_change_other_crime_annualised_rate = Column(Float)
    yoy_pct_change_other_theft_annualised_rate = Column(Float)
    yoy_pct_change_possession_of_weapons_annualised_rate = Column(Float)

# =====================================================================
# 1 OF 2: HISTORICAL TABLES (Housing Timeline)
# =====================================================================


class BoroughHousingHistorical(Base):
    __tablename__ = "borough_housing_historical"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ons_code = Column(String(10), ForeignKey("boroughs.ons_code"), nullable=False, index=True)
    year = Column(Integer, nullable=False)

    # Raw stats (identical structure to BoroughHousing)
    total_dwellings = Column(Integer)
    affordable_additions = Column(Float)
    band_d = Column(Integer)
    average_price = Column(Integer)
    net_additions = Column(Float)

    # Precomputed London Averages
    lon_average_price = Column(Float)
    lon_avg_affordable_additions = Column(Float)
    lon_avg_total_dwellings = Column(Float)
    lon_avg_net_additions = Column(Float)
    lon_avg_band_d = Column(Float)

    # Precomputed Percentage Differences
    pct_diff_average_price = Column(Float)
    pct_diff_affordable_additions = Column(Float)
    pct_diff_total_dwellings = Column(Float)
    pct_diff_net_additions = Column(Float)
    pct_diff_band_d = Column(Float)

    # Precomputed Year-on-Year Growth & Ratios
    yoy_pct_change_average_price = Column(Float)
    yoy_pct_change_total_dwellings = Column(Float)
    ratio_of_total_new_house_affordable = Column(Float)

    # Prevent duplicate year records for the same borough
    __table_args__ = (UniqueConstraint('ons_code', 'year', name='_borough_housing_year_uc'),)

# =====================================================================
# 2 OF 2: HISTORICAL TABLES (Police/Crime Timeline)
# =====================================================================


class BoroughPoliceHistorical(Base):
    __tablename__ = "borough_police_historical"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ons_code = Column(String(10), ForeignKey("boroughs.ons_code"), nullable=False, index=True)
    year = Column(Integer, nullable=False)

    # Raw Crime Annualised Rates (identical to BoroughPolice)
    anti_social_behaviour_annualised_rate = Column(Float)
    bicycle_theft_annualised_rate = Column(Float)
    burglary_annualised_rate = Column(Float)
    criminal_damage_arson_annualised_rate = Column(Float)
    drugs_annualised_rate = Column(Float)
    other_crime_annualised_rate = Column(Float)
    other_theft_annualised_rate = Column(Float)
    possession_of_weapons_annualised_rate = Column(Float)
    public_order_annualised_rate = Column(Float)
    robbery_annualised_rate = Column(Float)
    shoplifting_annualised_rate = Column(Float)
    theft_from_the_person_annualised_rate = Column(Float)
    vehicle_crime_annualised_rate = Column(Float)
    violent_crime_annualised_rate = Column(Float)

    # Precomputed London Averages
    lon_avg_anti_social_behaviour_annualised_rate = Column(Float)
    lon_avg_bicycle_theft_annualised_rate = Column(Float)
    lon_avg_burglary_annualised_rate = Column(Float)
    lon_avg_criminal_damage_arson_annualised_rate = Column(Float)
    lon_avg_drugs_annualised_rate = Column(Float)
    lon_avg_other_crime_annualised_rate = Column(Float)
    lon_avg_other_theft_annualised_rate = Column(Float)
    lon_avg_possession_of_weapons_annualised_rate = Column(Float)
    lon_avg_public_order_annualised_rate = Column(Float)
    lon_avg_robbery_annualised_rate = Column(Float)
    lon_avg_shoplifting_annualised_rate = Column(Float)
    lon_avg_theft_from_the_person_annualised_rate = Column(Float)
    lon_avg_vehicle_crime_annualised_rate = Column(Float)
    lon_avg_violent_crime_annualised_rate = Column(Float)

    # Precomputed Percentage Differences
    pct_diff_anti_social_behaviour_annualised_rate = Column(Float)
    pct_diff_bicycle_theft_annualised_rate = Column(Float)
    pct_diff_burglary_annualised_rate = Column(Float)
    pct_diff_criminal_damage_arson_annualised_rate = Column(Float)
    pct_diff_drugs_annualised_rate = Column(Float)
    pct_diff_other_crime_annualised_rate = Column(Float)
    pct_diff_other_theft_annualised_rate = Column(Float)
    pct_diff_possession_of_weapons_annualised_rate = Column(Float)
    pct_diff_public_order_annualised_rate = Column(Float)
    pct_diff_robbery_annualised_rate = Column(Float)
    pct_diff_shoplifting_annualised_rate = Column(Float)
    pct_diff_theft_from_the_person_annualised_rate = Column(Float)
    pct_diff_vehicle_crime_annualised_rate = Column(Float)
    pct_diff_violent_crime_annualised_rate = Column(Float)

    # Precomputed Year-on-Year Growth
    yoy_pct_change_anti_social_behaviour_annualised_rate = Column(Float)
    yoy_pct_change_bicycle_theft_annualised_rate = Column(Float)
    yoy_pct_change_burglary_annualised_rate = Column(Float)
    yoy_pct_change_criminal_damage_arson_annualised_rate = Column(Float)
    yoy_pct_change_drugs_annualised_rate = Column(Float)
    yoy_pct_change_other_crime_annualised_rate = Column(Float)
    yoy_pct_change_other_theft_annualised_rate = Column(Float)
    yoy_pct_change_possession_of_weapons_annualised_rate = Column(Float)

    # Prevent duplicate records for the same year in the same borough
    __table_args__ = (UniqueConstraint('ons_code', 'year', name='_borough_police_year_uc'),)
