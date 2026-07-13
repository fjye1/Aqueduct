CRIME_BUCKETS = {
    # Violent & Serious Crime
    "violent-crime": "Violent & Serious Crime",
    "possession-of-weapons": "Violent & Serious Crime",
    "robbery": "Violent & Serious Crime",

    # Property & Theft Crime
    "burglary": "Property & Theft Crime",
    "vehicle-crime": "Property & Theft Crime",
    "bicycle-theft": "Property & Theft Crime",
    "shoplifting": "Property & Theft Crime",
    "theft-from-the-person": "Property & Theft Crime",
    "other-theft": "Property & Theft Crime",

    # Quality of Life & Public Order
    "anti-social-behaviour": "Quality of Life & Public Order",
    "public-order": "Quality of Life & Public Order",
    "criminal-damage-arson": "Quality of Life & Public Order",
    "drugs": "Quality of Life & Public Order",

    # Other / Catch-all
    "other-crime": "Other",
    "all-crime": "Other"
}

def process_crime_record(api_record):
    """
    Takes a raw crime record from the police API and appends
    our custom analytical category.
    """
    raw_category = api_record.get("category", "other-crime")

    # Enrich the record with your custom bucket
    api_record["analytical_category"] = CRIME_BUCKETS.get(raw_category, "Other")
    return api_record
