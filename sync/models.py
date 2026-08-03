from sqlalchemy import Column, String, Integer, Float, Date, DateTime, ForeignKey, PrimaryKeyConstraint,UniqueConstraint
from sqlalchemy.orm import relationship


from sync.database import Base


class DistinctTable(Base):
    __tablename__ = "district_table"

    ons_code = Column(String(10), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    _built_at = Column(DateTime(timezone=True), nullable=True)

    # 1:1 or 1:N Relationship back-link to education data
    # uselist=False forces a 1:1 relationship on this side
    education = relationship(
        "EducationLondon",
        back_populates="borough",
        uselist=False
    )

    rent_quarterly = relationship(
        "RentQuarterly",
        back_populates="borough",
        cascade="all, delete-orphan"
    )

    # 1:Many Relationship for Housing Prices
    housing_price_quarterly = relationship(
        "HousingPriceQuarterly",
        back_populates="borough",
        cascade="all, delete-orphan",
    )

    housing_stock_annual = relationship(
        "HousingStockAnnual",
        back_populates="borough",
        cascade="all, delete-orphan",
    )

    police_police = relationship(
        "PolicePolice",
        back_populates="borough",
        cascade="all, delete-orphan",
    )


# =====================================================================
# 1 OF 1: DOMAIN EDUCATION TABLES (education_london)
# =====================================================================


class EducationLondon(Base):
    __tablename__ = "education_london"

    # Links 1:1 to the main boroughs table
    ons_code = Column(
        String(10),
        ForeignKey("distinct_table.ons_code"),
        primary_key=True,
    )

    # Reference
    borough_name = Column(String(100), nullable=False)
    year = Column(String(9), nullable=False)  # e.g. "2024-2025"

    # School Counts
    independent_school_count = Column(Float)
    public_funded_nursery = Column(Integer, default=0)
    public_funded_primary = Column(Integer, default=0)
    public_funded_secondary = Column(Integer, default=0)
    public_funded_school_count = Column(Integer, default=0)
    total_school_count = Column(Float)

    # Educational Performance
    gcse_attainment_8 = Column(Float)
    strong_pass_eng_maths = Column(Float)
    ks2_expectedstandard_read_write_maths = Column(Float)
    ks2_higherstandard_read_write_maths = Column(Float)

    # Ofsted
    ofsted_goodand_outstanding = Column(Integer)
    ofsted_london_average = Column(Float)

    # Rankings
    education_rank = Column(Integer)

    # Relationship back to DistinctTable
    borough = relationship("DistinctTable", back_populates="education")


# =====================================================================
# 1 OF 3: DOMAIN HOUSING TABLES (RentQuarterly)
# =====================================================================
class RentQuarterly(Base):
    __tablename__ = "rent_quarterly"

    # --- Composite Primary Key & Foreign Keys ---
    ons_code = Column(
        String(10),
        ForeignKey("distinct_table.ons_code"),
        primary_key=True,
        index=True,
    )
    year = Column(Integer, primary_key=True)
    quarter = Column(Integer, primary_key=True)

    # --- Time & Location Metadata ---
    borough_name = Column(String(100), nullable=False)
    quarter_label = Column(String(10), nullable=False)  # e.g., "Q1 '20"
    quarter_start_date = Column(Date, nullable=False, index=True)

    # --- Average Monthly Rent (£) ---
    rent_all = Column(Float, nullable=True)
    rent_one_bed = Column(Float, nullable=True)
    rent_two_bed = Column(Float, nullable=True)
    rent_three_bed = Column(Float, nullable=True)
    rent_four_plus_bed = Column(Float, nullable=True)

    # --- Year-over-Year Percentage Changes (%) ---
    yoy_all_pct = Column(Float, nullable=True)
    yoy_one_bed_pct = Column(Float, nullable=True)
    yoy_two_bed_pct = Column(Float, nullable=True)
    yoy_three_bed_pct = Column(Float, nullable=True)
    yoy_four_plus_bed_pct = Column(Float, nullable=True)

    # --- Quarter Rankings ---
    rank_rent_all = Column(Integer, nullable=True)
    rank_rent_one_bed = Column(Integer, nullable=True)
    rank_rent_two_bed = Column(Integer, nullable=True)
    rank_rent_three_bed = Column(Integer, nullable=True)
    rank_rent_four_plus_bed = Column(Integer, nullable=True)

    # --- Pipeline Metadata ---
    _transformed_at = Column(DateTime(timezone=True), nullable=True)

    # --- Relationship ---
    # Many rent records point back to 1 borough in DistinctTable
    borough = relationship("DistinctTable", back_populates="rent_quarterly")


# =====================================================================
# 2 OF 3: DOMAIN HOUSING TABLES (housing_price_quarterly)
# =====================================================================

class HousingPriceQuarterly(Base):
    __tablename__ = "housing_price_quarterly"

    # --- Composite Primary Key & Foreign Key ---
    ons_code = Column(
        String(10),
        ForeignKey("distinct_table.ons_code"),
        primary_key=True,
        index=True,
    )
    year = Column(Integer, primary_key=True)
    quarter = Column(Integer, primary_key=True)

    # --- Location & Time Metadata ---
    borough_name = Column(String(100), nullable=False)
    quarter_label = Column(String(10), nullable=False)  # e.g., "Q1 '21"
    quarter_start_date = Column(Date, nullable=False, index=True)

    # --- Metrics ---
    avg_price = Column(Float, nullable=True)
    yoy_growth_pct = Column(Float, nullable=True)

    # --- Pipeline Metadata (Standard PostgreSQL TIMESTAMPTZ) ---
    _gold_built_at = Column(DateTime(timezone=True), nullable=True)

    # --- Relationship ---
    borough = relationship("DistinctTable", back_populates="housing_price_quarterly")

# =====================================================================
# 3 OF 3: DOMAIN HOUSING TABLES (housing_stock_annual)
# =====================================================================

class HousingStockAnnual(Base):
    __tablename__ = "housing_stock_annual"

    # --- Composite Primary Key & Foreign Key ---
    ons_code = Column(
        String(10),
        ForeignKey("distinct_table.ons_code"),
        primary_key=True,
        index=True,
    )
    year = Column(Integer, primary_key=True)

    # --- Location & Time Metadata ---
    borough_name = Column(String(100), nullable=False)
    affordable_financial_year = Column(String(9), nullable=True)  # e.g. "2024-25"

    # --- Dwelling Counts & Additions ---
    total_dwellings = Column(Integer, nullable=True)
    net_additions = Column(Integer, nullable=True)

    # --- GLA-funded Affordable Housing ---
    affordable_starts = Column(Integer, nullable=True)
    affordable_completions = Column(Integer, nullable=True)

    # --- Council Tax ---
    band_d = Column(Integer, nullable=True)

    # --- Rankings ---
    rank_total_dwellings = Column(Integer, nullable=True)
    rank_net_additions = Column(Integer, nullable=True)
    rank_band_d_lowest = Column(Integer, nullable=True)

    # --- Pipeline Metadata ---
    _gold_built_at = Column(DateTime(timezone=True), nullable=True)

    # --- Relationship ---
    borough = relationship("DistinctTable", back_populates="housing_stock_annual")

# =====================================================================
# 1 OF 1: DOMAIN POLICING TABLES (police_police)
# =====================================================================

class PolicePolice(Base):
    __tablename__ = "police_police"

    # --- Composite Primary Key & Foreign Key ---
    ons_code = Column(
        String(10),
        ForeignKey("distinct_table.ons_code"),
        primary_key=True,
        index=True,
    )
    year = Column(Integer, primary_key=True)

    # --- Area & Demographics ---
    borough_name = Column(String(100), nullable=False)
    population = Column(Integer, nullable=True)

    # --- Annualised Counts (sum of 12 months) ---
    anti_social_behaviour_annualised_rate = Column(Float, nullable=True)
    bicycle_theft_annualised_rate = Column(Float, nullable=True)
    burglary_annualised_rate = Column(Float, nullable=True)
    criminal_damage_arson_annualised_rate = Column(Float, nullable=True)
    drugs_annualised_rate = Column(Float, nullable=True)
    other_crime_annualised_rate = Column(Float, nullable=True)
    other_theft_annualised_rate = Column(Float, nullable=True)
    possession_of_weapons_annualised_rate = Column(Float, nullable=True)
    public_order_annualised_rate = Column(Float, nullable=True)
    robbery_annualised_rate = Column(Float, nullable=True)
    shoplifting_annualised_rate = Column(Float, nullable=True)
    theft_from_the_person_annualised_rate = Column(Float, nullable=True)
    vehicle_crime_annualised_rate = Column(Float, nullable=True)
    violent_crime_annualised_rate = Column(Float, nullable=True)
    total_crimes_annualised = Column(Float, nullable=True)

    # --- Per 1,000 Population Rates ---
    total_crimes_per_1000 = Column(Float, nullable=True)
    anti_social_behaviour_per_1000 = Column(Float, nullable=True)
    bicycle_theft_per_1000 = Column(Float, nullable=True)
    burglary_per_1000 = Column(Float, nullable=True)
    criminal_damage_arson_per_1000 = Column(Float, nullable=True)
    drugs_per_1000 = Column(Float, nullable=True)
    other_crime_per_1000 = Column(Float, nullable=True)
    other_theft_per_1000 = Column(Float, nullable=True)
    possession_of_weapons_per_1000 = Column(Float, nullable=True)
    public_order_per_1000 = Column(Float, nullable=True)
    robbery_per_1000 = Column(Float, nullable=True)
    shoplifting_per_1000 = Column(Float, nullable=True)
    theft_from_the_person_per_1000 = Column(Float, nullable=True)
    vehicle_crime_per_1000 = Column(Float, nullable=True)
    violent_crime_per_1000 = Column(Float, nullable=True)

    # --- London Averages ---
    lon_avg_total_crimes_per_1000 = Column(Float, nullable=True)
    lon_avg_anti_social_behaviour_per_1000 = Column(Float, nullable=True)
    lon_avg_bicycle_theft_per_1000 = Column(Float, nullable=True)
    lon_avg_burglary_per_1000 = Column(Float, nullable=True)
    lon_avg_criminal_damage_arson_per_1000 = Column(Float, nullable=True)
    lon_avg_drugs_per_1000 = Column(Float, nullable=True)
    lon_avg_other_crime_per_1000 = Column(Float, nullable=True)
    lon_avg_other_theft_per_1000 = Column(Float, nullable=True)
    lon_avg_possession_of_weapons_per_1000 = Column(Float, nullable=True)
    lon_avg_public_order_per_1000 = Column(Float, nullable=True)
    lon_avg_robbery_per_1000 = Column(Float, nullable=True)
    lon_avg_shoplifting_per_1000 = Column(Float, nullable=True)
    lon_avg_theft_from_the_person_per_1000 = Column(Float, nullable=True)
    lon_avg_vehicle_crime_per_1000 = Column(Float, nullable=True)
    lon_avg_violent_crime_per_1000 = Column(Float, nullable=True)

    # --- % Difference vs London Average ---
    pct_diff_total_crimes_per_1000 = Column(Float, nullable=True)
    pct_diff_anti_social_behaviour_per_1000 = Column(Float, nullable=True)
    pct_diff_bicycle_theft_per_1000 = Column(Float, nullable=True)
    pct_diff_burglary_per_1000 = Column(Float, nullable=True)
    pct_diff_criminal_damage_arson_per_1000 = Column(Float, nullable=True)
    pct_diff_drugs_per_1000 = Column(Float, nullable=True)
    pct_diff_other_crime_per_1000 = Column(Float, nullable=True)
    pct_diff_other_theft_per_1000 = Column(Float, nullable=True)
    pct_diff_possession_of_weapons_per_1000 = Column(Float, nullable=True)
    pct_diff_public_order_per_1000 = Column(Float, nullable=True)
    pct_diff_robbery_per_1000 = Column(Float, nullable=True)
    pct_diff_shoplifting_per_1000 = Column(Float, nullable=True)
    pct_diff_theft_from_the_person_per_1000 = Column(Float, nullable=True)
    pct_diff_vehicle_crime_per_1000 = Column(Float, nullable=True)
    pct_diff_violent_crime_per_1000 = Column(Float, nullable=True)

    # --- YoY % Changes ---
    yoy_pct_change_total_crimes_per_1000 = Column(Float, nullable=True)
    yoy_pct_change_anti_social_behaviour_per_1000 = Column(Float, nullable=True)
    yoy_pct_change_bicycle_theft_per_1000 = Column(Float, nullable=True)
    yoy_pct_change_burglary_per_1000 = Column(Float, nullable=True)
    yoy_pct_change_criminal_damage_arson_per_1000 = Column(Float, nullable=True)
    yoy_pct_change_drugs_per_1000 = Column(Float, nullable=True)
    yoy_pct_change_other_crime_per_1000 = Column(Float, nullable=True)
    yoy_pct_change_other_theft_per_1000 = Column(Float, nullable=True)
    yoy_pct_change_possession_of_weapons_per_1000 = Column(Float, nullable=True)
    yoy_pct_change_public_order_per_1000 = Column(Float, nullable=True)
    yoy_pct_change_robbery_per_1000 = Column(Float, nullable=True)
    yoy_pct_change_shoplifting_per_1000 = Column(Float, nullable=True)
    yoy_pct_change_theft_from_the_person_per_1000 = Column(Float, nullable=True)
    yoy_pct_change_vehicle_crime_per_1000 = Column(Float, nullable=True)
    yoy_pct_change_violent_crime_per_1000 = Column(Float, nullable=True)

    # --- Rankings ---
    rank_total_crimes_per_1000 = Column(Integer, nullable=True)
    rank_total_crimes_annualised = Column(Integer, nullable=True)
    safety_rank_total_crimes_per_1000 = Column(Integer, nullable=True)
    safety_rank_total_crimes_annualised = Column(Integer, nullable=True)

    # --- Relationship ---
    borough = relationship("DistinctTable", back_populates="police_police")


# =====================================================================
# Infra
# =====================================================================

# class BoroughInfrastructure(Base):
#     __tablename__ = "borough_infrastructure"
#
#     # Links 1:1 to the main boroughs table
#     ons_code = Column(String(10), ForeignKey("boroughs.ons_code"), primary_key=True)
#
#     # Accessibility Metrics
#     ptal = Column(String(10))
#     avg_ptal = Column(Float)
#     pct_diff_from_avg = Column(Float)
#
#     # Transit Asset Counts
#     bus_count = Column(Integer, default=0)
#     dlr_count = Column(Integer, default=0)
#     elizabeth_count = Column(Integer, default=0)
#     overground_count = Column(Integer, default=0)
#     tramlink_count = Column(Integer, default=0)
#     tube_count = Column(Integer, default=0)
#
#     # List of intersecting transit line names (e.g., "Northern, Piccadilly")
#     line_name = Column(String(255))


# =====================================================================
# 4 OF 4: DOMAIN STATIC TABLES (Police/Crime - Current State)
# =====================================================================
# class BoroughPolice(Base):
#     __tablename__ = "borough_police"
#
#     # Links 1:1 to the main boroughs table for the most recent year's data
#     ons_code = Column(String(10), ForeignKey("boroughs.ons_code"), primary_key=True)
#     year = Column(Integer)
#
#     # Raw Crime Annualised Rates
#     anti_social_behaviour_annualised_rate = Column(Float)
#     bicycle_theft_annualised_rate = Column(Float)
#     burglary_annualised_rate = Column(Float)
#     criminal_damage_arson_annualised_rate = Column(Float)
#     drugs_annualised_rate = Column(Float)
#     other_crime_annualised_rate = Column(Float)
#     other_theft_annualised_rate = Column(Float)
#     possession_of_weapons_annualised_rate = Column(Float)
#     public_order_annualised_rate = Column(Float)
#     robbery_annualised_rate = Column(Float)
#     shoplifting_annualised_rate = Column(Float)
#     theft_from_the_person_annualised_rate = Column(Float)
#     vehicle_crime_annualised_rate = Column(Float)
#     violent_crime_annualised_rate = Column(Float)
#
#     # Precomputed London Averages
#     lon_avg_anti_social_behaviour_annualised_rate = Column(Float)
#     lon_avg_bicycle_theft_annualised_rate = Column(Float)
#     lon_avg_burglary_annualised_rate = Column(Float)
#     lon_avg_criminal_damage_arson_annualised_rate = Column(Float)
#     lon_avg_drugs_annualised_rate = Column(Float)
#     lon_avg_other_crime_annualised_rate = Column(Float)
#     lon_avg_other_theft_annualised_rate = Column(Float)
#     lon_avg_possession_of_weapons_annualised_rate = Column(Float)
#     lon_avg_public_order_annualised_rate = Column(Float)
#     lon_avg_robbery_annualised_rate = Column(Float)
#     lon_avg_shoplifting_annualised_rate = Column(Float)
#     lon_avg_theft_from_the_person_annualised_rate = Column(Float)
#     lon_avg_vehicle_crime_annualised_rate = Column(Float)
#     lon_avg_violent_crime_annualised_rate = Column(Float)
#
#     # Precomputed Percentage Differences from London Average
#     pct_diff_anti_social_behaviour_annualised_rate = Column(Float)
#     pct_diff_bicycle_theft_annualised_rate = Column(Float)
#     pct_diff_burglary_annualised_rate = Column(Float)
#     pct_diff_criminal_damage_arson_annualised_rate = Column(Float)
#     pct_diff_drugs_annualised_rate = Column(Float)
#     pct_diff_other_crime_annualised_rate = Column(Float)
#     pct_diff_other_theft_annualised_rate = Column(Float)
#     pct_diff_possession_of_weapons_annualised_rate = Column(Float)
#     pct_diff_public_order_annualised_rate = Column(Float)
#     pct_diff_robbery_annualised_rate = Column(Float)
#     pct_diff_shoplifting_annualised_rate = Column(Float)
#     pct_diff_theft_from_the_person_annualised_rate = Column(Float)
#     pct_diff_vehicle_crime_annualised_rate = Column(Float)
#     pct_diff_violent_crime_annualised_rate = Column(Float)
#
#     # Precomputed Year-on-Year Growth
#     yoy_pct_change_anti_social_behaviour_annualised_rate = Column(Float)
#     yoy_pct_change_bicycle_theft_annualised_rate = Column(Float)
#     yoy_pct_change_burglary_annualised_rate = Column(Float)
#     yoy_pct_change_criminal_damage_arson_annualised_rate = Column(Float)
#     yoy_pct_change_drugs_annualised_rate = Column(Float)
#     yoy_pct_change_other_crime_annualised_rate = Column(Float)
#     yoy_pct_change_other_theft_annualised_rate = Column(Float)
#     yoy_pct_change_possession_of_weapons_annualised_rate = Column(Float)

# =====================================================================
# 1 OF 2: HISTORICAL TABLES (Housing Timeline)
# =====================================================================


# class BoroughHousingHistorical(Base):
#     __tablename__ = "borough_housing_historical"
#
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     ons_code = Column(String(10), ForeignKey("boroughs.ons_code"), nullable=False, index=True)
#     year = Column(Integer, nullable=False)
#
#     # Raw stats (identical structure to BoroughHousing)
#     total_dwellings = Column(Integer)
#     affordable_additions = Column(Float)
#     band_d = Column(Integer)
#     average_price = Column(Integer)
#     net_additions = Column(Float)
#
#     # Precomputed London Averages
#     lon_average_price = Column(Float)
#     lon_avg_affordable_additions = Column(Float)
#     lon_avg_total_dwellings = Column(Float)
#     lon_avg_net_additions = Column(Float)
#     lon_avg_band_d = Column(Float)
#
#     # Precomputed Percentage Differences
#     pct_diff_average_price = Column(Float)
#     pct_diff_affordable_additions = Column(Float)
#     pct_diff_total_dwellings = Column(Float)
#     pct_diff_net_additions = Column(Float)
#     pct_diff_band_d = Column(Float)
#
#     # Precomputed Year-on-Year Growth & Ratios
#     yoy_pct_change_average_price = Column(Float)
#     yoy_pct_change_total_dwellings = Column(Float)
#     ratio_of_total_new_house_affordable = Column(Float)
#
#     # Prevent duplicate year records for the same borough
#     __table_args__ = (UniqueConstraint('ons_code', 'year', name='_borough_housing_year_uc'),)

# =====================================================================
# 2 OF 2: HISTORICAL TABLES (Police/Crime Timeline)
# =====================================================================


# class BoroughPoliceHistorical(Base):
#     __tablename__ = "borough_police_historical"
#
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     ons_code = Column(String(10), ForeignKey("boroughs.ons_code"), nullable=False, index=True)
#     year = Column(Integer, nullable=False)
#
#     # Raw Crime Annualised Rates (identical to BoroughPolice)
#     anti_social_behaviour_annualised_rate = Column(Float)
#     bicycle_theft_annualised_rate = Column(Float)
#     burglary_annualised_rate = Column(Float)
#     criminal_damage_arson_annualised_rate = Column(Float)
#     drugs_annualised_rate = Column(Float)
#     other_crime_annualised_rate = Column(Float)
#     other_theft_annualised_rate = Column(Float)
#     possession_of_weapons_annualised_rate = Column(Float)
#     public_order_annualised_rate = Column(Float)
#     robbery_annualised_rate = Column(Float)
#     shoplifting_annualised_rate = Column(Float)
#     theft_from_the_person_annualised_rate = Column(Float)
#     vehicle_crime_annualised_rate = Column(Float)
#     violent_crime_annualised_rate = Column(Float)
#
#     # Precomputed London Averages
#     lon_avg_anti_social_behaviour_annualised_rate = Column(Float)
#     lon_avg_bicycle_theft_annualised_rate = Column(Float)
#     lon_avg_burglary_annualised_rate = Column(Float)
#     lon_avg_criminal_damage_arson_annualised_rate = Column(Float)
#     lon_avg_drugs_annualised_rate = Column(Float)
#     lon_avg_other_crime_annualised_rate = Column(Float)
#     lon_avg_other_theft_annualised_rate = Column(Float)
#     lon_avg_possession_of_weapons_annualised_rate = Column(Float)
#     lon_avg_public_order_annualised_rate = Column(Float)
#     lon_avg_robbery_annualised_rate = Column(Float)
#     lon_avg_shoplifting_annualised_rate = Column(Float)
#     lon_avg_theft_from_the_person_annualised_rate = Column(Float)
#     lon_avg_vehicle_crime_annualised_rate = Column(Float)
#     lon_avg_violent_crime_annualised_rate = Column(Float)
#
#     # Precomputed Percentage Differences
#     pct_diff_anti_social_behaviour_annualised_rate = Column(Float)
#     pct_diff_bicycle_theft_annualised_rate = Column(Float)
#     pct_diff_burglary_annualised_rate = Column(Float)
#     pct_diff_criminal_damage_arson_annualised_rate = Column(Float)
#     pct_diff_drugs_annualised_rate = Column(Float)
#     pct_diff_other_crime_annualised_rate = Column(Float)
#     pct_diff_other_theft_annualised_rate = Column(Float)
#     pct_diff_possession_of_weapons_annualised_rate = Column(Float)
#     pct_diff_public_order_annualised_rate = Column(Float)
#     pct_diff_robbery_annualised_rate = Column(Float)
#     pct_diff_shoplifting_annualised_rate = Column(Float)
#     pct_diff_theft_from_the_person_annualised_rate = Column(Float)
#     pct_diff_vehicle_crime_annualised_rate = Column(Float)
#     pct_diff_violent_crime_annualised_rate = Column(Float)
#
#     # Precomputed Year-on-Year Growth
#     yoy_pct_change_anti_social_behaviour_annualised_rate = Column(Float)
#     yoy_pct_change_bicycle_theft_annualised_rate = Column(Float)
#     yoy_pct_change_burglary_annualised_rate = Column(Float)
#     yoy_pct_change_criminal_damage_arson_annualised_rate = Column(Float)
#     yoy_pct_change_drugs_annualised_rate = Column(Float)
#     yoy_pct_change_other_crime_annualised_rate = Column(Float)
#     yoy_pct_change_other_theft_annualised_rate = Column(Float)
#     yoy_pct_change_possession_of_weapons_annualised_rate = Column(Float)
#
#     # Prevent duplicate records for the same year in the same borough
#     __table_args__ = (UniqueConstraint('ons_code', 'year', name='_borough_police_year_uc'),)
